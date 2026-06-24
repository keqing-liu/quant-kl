"""数据管理层：把下载到的行情增量写入 SQLite，并记录数据更新日志。"""

from datetime import date, timedelta

import pandas as pd

from database.db_utils import (
    get_connection,
    get_latest_date,
    log_data_update,
)

from data_fetch.fetch_cboe_market import (
    build_cboe_index_internal_symbol,
    download_cboe_index_data,
)
from data_fetch.fetch_etf import download_etf_data
from data_fetch.fetch_stock import download_stock_data
from data_fetch.fetch_us_market import (
    build_us_index_symbol,
    build_us_symbol,
    download_us_index_data,
    download_us_market_data,
    get_fmp_basic_start_date,
)


class DataManager:

    def _is_us_today_no_new_data_error(self, error, latest_date_before, download_kwargs):
        """判断美股日常重复更新时的“今天暂无新日线”情况。"""

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
        """更新单个 symbol 的价格数据，并写入 data_update_log。"""

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

            latest_date_before = get_latest_date(symbol)

            latest_date_dt = None
            if latest_date_before is not None:
                latest_date_dt = pd.to_datetime(latest_date_before)

            print(f"{symbol} 最新日期: {latest_date_before}")

            # =========================
            # 2. 下载数据
            # =========================

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
                log_data_update(
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
                log_data_update(
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

            conn = get_connection()
            cursor = conn.cursor()

            sql = """
            INSERT OR IGNORE INTO price_data (
                symbol,
                date,
                open,
                high,
                low,
                close,
                volume
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """

            data = list(
                df.itertuples(index=False, name=None)
            )

            cursor.executemany(sql, data)

            # 注意：
            # len(df) 是准备写入的行数；
            # cursor.rowcount 是实际插入的行数。
            # 因为 INSERT OR IGNORE 会跳过重复记录，所以两者可能不同。
            rows_inserted = cursor.rowcount

            conn.commit()
            conn.close()

            # =========================
            # 7. 写入成功日志
            # =========================

            log_data_update(
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
                log_data_update(
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

            log_data_update(
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
        """计算 FMP Basic 下载窗口。"""

        if start_date is not None:
            # 用户在 CLI 里显式给了 --start-date 时，以用户输入为准。
            resolved_start_date = pd.to_datetime(start_date).strftime("%Y-%m-%d")
        elif full_history:
            # FMP Basic 免费档历史范围有限，默认按最近约 5 年请求。
            resolved_start_date = get_fmp_basic_start_date()
        else:
            latest_date_before = get_latest_date(symbol)
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

    def update_etf(self, symbol):

        self._update_price_data(
            symbol=symbol,
            download_func=download_etf_data,
            asset_type="ETF",
            data_source="akshare_sina",
        )

    def update_stock(self, symbol):

        self._update_price_data(
            symbol=symbol,
            download_func=download_stock_data,
            asset_type="STOCK",
            data_source="akshare",
        )

    def update_us_stock(self, ticker):
        """更新单只美国股票行情。"""

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
        """更新单只美国 ETF 行情。"""

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
