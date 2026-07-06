"""价格数据更新服务。

当前 DataManager 保留为 main.py / quant.py 使用的稳定入口。

分层理解：
1. data_fetch/ 只负责外部接口下载，并返回统一的行情 DataFrame。
2. repositories/ 只负责 SQLite 读写，例如 price_data 和 data_update_log。
3. DataManager 负责业务流程编排：查最新日期、决定下载窗口、调用下载、
   过滤增量、调用 repository 入库并记录日志。
"""

from datetime import date, timedelta

import pandas as pd

from data_fetch.fetch_cboe_market import (
    build_cboe_index_internal_symbol,
    download_cboe_index_data,
)
from data_fetch.fetch_alpha_vantage_ca import (
    build_ca_stock_symbol,
    download_alpha_vantage_ca_stock_data,
)
from data_fetch.fetch_etf import download_etf_data
from data_fetch.fetch_fred_treasury import (
    FRED_TREASURY_SPREAD_SYMBOL,
    build_fred_treasury_internal_symbol,
    download_fred_treasury_data,
    get_fred_default_start_date,
)
from data_fetch.fetch_stock import download_stock_data
from data_fetch.fetch_us_market import (
    build_us_index_symbol,
    build_us_symbol,
    download_us_index_data,
    download_us_market_data,
    get_fmp_basic_start_date,
)
from database.db_utils import get_connection
from repositories.price_repository import (
    get_latest_price_date,
    insert_price_data,
)
from repositories.update_log_repository import log_price_update


class DataManager:
    """价格更新流程编排器。

    这个类现在更接近 services/price_update_service.py 的角色：
    它不应该关心外部接口的解析细节，也尽量不直接写 SQL。
    """

    def _is_us_today_no_new_data_error(self, error, latest_date_before, download_kwargs):
        """判断美股日常重复更新时的“今天暂无新日线”情况。

        这是 service 层的业务规则：同样的接口错误，在日常重复更新场景
        可以被解释为 no_new_data，而不是 failed。
        """

        if latest_date_before is None:
            return False

        start_date = download_kwargs.get("start_date")
        end_date = download_kwargs.get("end_date")
        today = date.today().strftime("%Y-%m-%d")

        if start_date != today or end_date != today:
            return False

        message = str(error)

        return (
            "FMP 下载失败" in message
            and "FMP 返回空数据" in message
            and (
                "Twelve Data 返回空数据" in message
                or "HTTP Error 400: Bad Request" in message
            )
        )

    def _update_price_data(
        self,
        symbol,
        download_func,
        asset_type,
        data_source,
        full_history_on_empty_db=False,
        force_full_history=False,
        max_pages=None,
        download_kwargs=None,
    ):
        """更新单个 symbol 的价格数据，并写入 data_update_log。

        这是当前价格更新的统一流程：
        repository 查库 -> data_fetch 下载 -> service 过滤增量 ->
        repository 写库 -> repository 写日志。
        """

        latest_date_before = None
        rows_downloaded = 0
        rows_inserted = 0
        start_date = None
        end_date = None
        download_kwargs = download_kwargs or {}

        try:
            # =========================
            # 1. 查询数据库已有最新日期
            # =========================

            # Repository 职责：查询 price_data 里已有的最新日期。
            latest_date_before = get_latest_price_date(symbol)

            latest_date_dt = None
            if latest_date_before is not None:
                latest_date_dt = pd.to_datetime(latest_date_before)

            print(f"{symbol} 最新日期: {latest_date_before}")

            # =========================
            # 2. 下载数据
            # =========================

            # data_fetch 职责：download_func 来自 data_fetch/*，只负责下载并
            # 返回 date/open/high/low/close/volume 这套统一字段。
            if force_full_history:
                df = download_func(
                    symbol,
                    full_history=True,
                    max_pages=max_pages,
                    **download_kwargs,
                )
            elif full_history_on_empty_db and latest_date_before is None:
                df = download_func(symbol, full_history=True, **download_kwargs)
            else:
                df = download_func(symbol, **download_kwargs)

            # 如果下载函数返回 None 或空 DataFrame，也要写日志。
            if df is None or df.empty:
                # Repository 职责：把本次更新结果写入 data_update_log。
                log_price_update(
                    symbol=symbol,
                    asset_type=asset_type,
                    latest_date_before=latest_date_before,
                    start_date=None,
                    end_date=None,
                    rows_downloaded=0,
                    rows_inserted=0,
                    status="empty",
                    message="数据接口返回空数据",
                    data_source=data_source,
                )

                print(f"{symbol} 数据接口返回空数据")
                return

            rows_downloaded = len(df)

            # =========================
            # 3. 整理日期
            # =========================

            df["date"] = pd.to_datetime(df["date"])

            df = df.sort_values("date").reset_index(drop=True)

            start_date = df["date"].min().strftime("%Y-%m-%d")
            end_date = df["date"].max().strftime("%Y-%m-%d")

            # =========================
            # 4. 过滤增量数据
            # =========================

            if latest_date_dt is not None and not force_full_history:
                df = df[df["date"] > latest_date_dt]

            # 如果接口有数据，但没有比数据库更新的数据，也要写日志。
            if df.empty:
                # Repository 职责：把“无新增数据”的结果写入日志。
                log_price_update(
                    symbol=symbol,
                    asset_type=asset_type,
                    latest_date_before=latest_date_before,
                    start_date=start_date,
                    end_date=end_date,
                    rows_downloaded=rows_downloaded,
                    rows_inserted=0,
                    status="no_new_data",
                    message="接口有数据，但数据库已经是最新",
                    data_source=data_source,
                )

                print(f"{symbol} 无需更新")
                return

            # =========================
            # 5. 添加 symbol，并保留 price_data 需要的列
            # =========================

            df["symbol"] = symbol

            df = df[[
                "symbol",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]]

            # 去掉下载结果内部的重复日期。
            df = df.drop_duplicates(
                subset=["symbol", "date"]
            )

            # SQLite 里 date 保存成 YYYY-MM-DD 文本。
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")

            # 增量数据实际起止日期。
            inserted_start_date = df["date"].min()
            inserted_end_date = df["date"].max()

            # =========================
            # 6. 写入 price_data
            # =========================

            # Repository 职责：执行 INSERT OR IGNORE 并返回实际插入行数。
            # 注意：len(df) 是准备写入的行数；rows_inserted 是实际新增行数。
            rows_inserted = insert_price_data(df)

            # =========================
            # 7. 写入成功日志
            # =========================

            # Repository 职责：记录成功日志。
            log_price_update(
                symbol=symbol,
                asset_type=asset_type,
                latest_date_before=latest_date_before,
                start_date=inserted_start_date,
                end_date=inserted_end_date,
                rows_downloaded=rows_downloaded,
                rows_inserted=rows_inserted,
                status="success",
                message="数据更新成功",
                data_source=data_source,
            )

            print(
                f"{symbol} 更新完成："
                f"下载 {rows_downloaded} 行，"
                f"实际新增 {rows_inserted} 行"
            )

        except Exception as e:
            # =========================
            # 8. 写入失败日志，或识别“今天暂无新美股日线”的重复更新
            # =========================

            if (
                data_source == "fmp_twelvedata"
                and self._is_us_today_no_new_data_error(
                    e,
                    latest_date_before,
                    download_kwargs,
                )
            ):
                # Repository 职责：记录已识别的 no_new_data 日志。
                log_price_update(
                    symbol=symbol,
                    asset_type=asset_type,
                    latest_date_before=latest_date_before,
                    start_date=download_kwargs.get("start_date"),
                    end_date=download_kwargs.get("end_date"),
                    rows_downloaded=0,
                    rows_inserted=0,
                    status="no_new_data",
                    message="今天暂无新的美股日线数据，无需更新",
                    data_source=data_source,
                )

                print(f"{symbol} 无需更新：今天暂无新的美股日线数据")
                return

            # Repository 职责：记录失败日志。
            log_price_update(
                symbol=symbol,
                asset_type=asset_type,
                latest_date_before=latest_date_before,
                start_date=start_date,
                end_date=end_date,
                rows_downloaded=rows_downloaded,
                rows_inserted=rows_inserted,
                status="failed",
                message=str(e),
                data_source=data_source,
            )

            print(f"{symbol} 更新失败: {e}")

    def _get_fmp_download_kwargs(self, symbol, start_date=None, end_date=None, full_history=False):
        """计算 FMP Basic 下载窗口。

        这是 service 层的决策逻辑：根据数据库最新日期和用户参数，
        决定这次应该向外部数据源请求哪个日期区间。
        """

        if start_date is not None:
            # 用户在 CLI 里显式给了 --start-date 时，以用户输入为准。
            resolved_start_date = pd.to_datetime(start_date).strftime("%Y-%m-%d")
        elif full_history:
            # FMP Basic 免费档历史范围有限，默认按最近约 5 年请求。
            resolved_start_date = get_fmp_basic_start_date()
        else:
            latest_date_before = get_latest_price_date(symbol)
            if latest_date_before is None:
                resolved_start_date = get_fmp_basic_start_date()
            else:
                # 日常更新只请求数据库最新日期之后的数据，减少 API 调用压力。
                resolved_start_date = (
                    pd.to_datetime(latest_date_before) + timedelta(days=1)
                ).strftime("%Y-%m-%d")

        resolved_end_date = end_date or date.today().strftime("%Y-%m-%d")

        return {
            # download_kwargs 会被 _update_price_data 原样传给下载函数。
            "start_date": resolved_start_date,
            "end_date": resolved_end_date,
            "adjust_prices": True,
        }

    def _get_fred_download_kwargs(self, symbol):
        """计算 FRED 日常下载窗口。"""

        latest_date_before = get_latest_price_date(symbol)
        if latest_date_before is None:
            resolved_start_date = get_fred_default_start_date()
        else:
            resolved_start_date = (
                pd.to_datetime(latest_date_before) + timedelta(days=1)
            ).strftime("%Y-%m-%d")

        return {
            "start_date": resolved_start_date,
            "end_date": date.today().strftime("%Y-%m-%d"),
        }

    def update_etf(self, symbol):
        """服务入口：更新单只中国 ETF。"""

        self._update_price_data(
            symbol=symbol,
            download_func=download_etf_data,
            asset_type="ETF",
            data_source="akshare_sina",
        )

    def update_stock(self, symbol):
        """服务入口：更新单只 A 股股票。"""

        self._update_price_data(
            symbol=symbol,
            download_func=download_stock_data,
            asset_type="STOCK",
            data_source="akshare",
        )

    def update_ca_stock(self, ticker):
        """服务入口：更新单只加拿大股票行情。"""

        symbol = build_ca_stock_symbol(ticker)
        self._update_price_data(
            symbol=symbol,
            download_func=download_alpha_vantage_ca_stock_data,
            asset_type="CA_STOCK",
            data_source="alpha_vantage",
        )

    def update_us_stock(self, ticker):
        """服务入口：更新单只美国股票行情。"""

        symbol = build_us_symbol(ticker)
        self._update_price_data(
            symbol=symbol,
            download_func=download_us_market_data,
            asset_type="US_STOCK",
            data_source="fmp_twelvedata",
            full_history_on_empty_db=True,
            download_kwargs=self._get_fmp_download_kwargs(symbol),
        )

    def update_us_etf(self, ticker):
        """服务入口：更新单只美国 ETF 行情。"""

        symbol = build_us_symbol(ticker)
        self._update_price_data(
            symbol=symbol,
            download_func=download_us_market_data,
            asset_type="US_ETF",
            data_source="fmp_twelvedata",
            full_history_on_empty_db=True,
            download_kwargs=self._get_fmp_download_kwargs(symbol),
        )

    def update_us_index(self, symbol):
        """更新单个美国指数行情。"""

        internal_symbol = build_us_index_symbol(symbol)
        self._update_price_data(
            symbol=internal_symbol,
            download_func=download_us_index_data,
            asset_type="US_INDEX",
            data_source="fmp_twelvedata",
            full_history_on_empty_db=True,
            download_kwargs=self._get_fmp_download_kwargs(internal_symbol),
        )

    def update_us_market_indicator(self, symbol):
        """更新单个 Cboe 市场风险指标。"""

        self._update_price_data(
            symbol=build_cboe_index_internal_symbol(symbol),
            download_func=download_cboe_index_data,
            asset_type="US_MARKET_INDICATOR",
            data_source="cboe",
        )

    def update_us_treasury_yield(self, series_id):
        """更新单个 FRED 美国国债收益率序列。"""

        symbol = build_fred_treasury_internal_symbol(series_id)
        self._update_price_data(
            symbol=symbol,
            download_func=download_fred_treasury_data,
            asset_type="US_TREASURY_YIELD",
            data_source="fred",
            download_kwargs=self._get_fred_download_kwargs(symbol),
        )

    def update_us_treasury_spread(self):
        """按同日 10Y - 2Y 生成 FRED 美债收益率利差序列。"""

        symbol = FRED_TREASURY_SPREAD_SYMBOL
        latest_date_before = get_latest_price_date(symbol)

        sql = """
        SELECT
            d10.date,
            d10.close - d2.close AS close
        FROM price_data AS d10
        JOIN price_data AS d2
        ON d10.date = d2.date
        WHERE d10.symbol = ?
          AND d2.symbol = ?
        ORDER BY d10.date
        """

        conn = None
        try:
            conn = get_connection()
            df = pd.read_sql(
                sql,
                conn,
                params=(
                    build_fred_treasury_internal_symbol("DGS10"),
                    build_fred_treasury_internal_symbol("DGS2"),
                ),
            )
        finally:
            if conn is not None:
                conn.close()

        if df.empty:
            log_price_update(
                symbol=symbol,
                asset_type="US_TREASURY_YIELD",
                latest_date_before=latest_date_before,
                rows_downloaded=0,
                rows_inserted=0,
                status="empty",
                message="DGS10/DGS2 无共同日期，无法生成利差",
                data_source="fred_local_spread",
            )
            print(f"{symbol} 无共同日期，无法生成利差")
            return

        latest_date_dt = None
        if latest_date_before is not None:
            latest_date_dt = pd.to_datetime(latest_date_before)
            df["date"] = pd.to_datetime(df["date"])
            df = df[df["date"] > latest_date_dt]
        else:
            df["date"] = pd.to_datetime(df["date"])

        if df.empty:
            log_price_update(
                symbol=symbol,
                asset_type="US_TREASURY_YIELD",
                latest_date_before=latest_date_before,
                rows_downloaded=0,
                rows_inserted=0,
                status="no_new_data",
                message="DGS10/DGS2 没有新的共同日期",
                data_source="fred_local_spread",
            )
            print(f"{symbol} 无需更新")
            return

        df["open"] = df["close"]
        df["high"] = df["close"]
        df["low"] = df["close"]
        df["volume"] = 0
        df["symbol"] = symbol
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        price_df = df[[
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]]
        rows_inserted = insert_price_data(price_df)
        start_date = price_df["date"].min()
        end_date = price_df["date"].max()

        log_price_update(
            symbol=symbol,
            asset_type="US_TREASURY_YIELD",
            latest_date_before=latest_date_before,
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=len(price_df),
            rows_inserted=rows_inserted,
            status="success",
            message="FRED 10Y-2Y 利差生成成功",
            data_source="fred_local_spread",
        )

        print(
            f"{symbol} 更新完成：生成 {len(price_df)} 行，"
            f"实际新增 {rows_inserted} 行"
        )

    def backfill_stooq_symbol(self, symbol, max_pages=None, start_date=None, end_date=None):
        """只补一个美国股票/ETF/指数的历史行情。"""

        normalized = str(symbol).strip()
        normalized_lower = normalized.lower()

        if (
            normalized.startswith("^")
            or normalized_lower.startswith("stooq_")
            or normalized_lower in {"ndq", "nasdaq"}
        ):
            internal_symbol = build_us_index_symbol(normalized)
            self._update_price_data(
                symbol=internal_symbol,
                download_func=download_us_index_data,
                asset_type="US_INDEX",
                data_source="fmp_twelvedata",
                force_full_history=True,
                max_pages=max_pages,
                download_kwargs=self._get_fmp_download_kwargs(
                    internal_symbol,
                    start_date=start_date,
                    end_date=end_date,
                    full_history=True,
                ),
            )
            return

        internal_symbol = build_us_symbol(normalized)
        self._update_price_data(
            symbol=internal_symbol,
            download_func=download_us_market_data,
            asset_type="US_STOCK",
            data_source="fmp_twelvedata",
            force_full_history=True,
            max_pages=max_pages,
            download_kwargs=self._get_fmp_download_kwargs(
                internal_symbol,
                start_date=start_date,
                end_date=end_date,
                full_history=True,
            ),
        )
