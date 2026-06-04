"""数据管理层：把下载到的行情增量写入 SQLite，并记录数据更新日志。"""

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
    build_stooq_internal_symbol,
    build_us_symbol,
    download_stooq_data,
    download_us_market_data,
)


class DataManager:

    def _update_price_data(
        self,
        symbol,
        download_func,
        asset_type,
        data_source,
    ):
        """更新单个 symbol 的价格数据，并写入 data_update_log。"""

        latest_date_before = None
        rows_downloaded = 0
        rows_inserted = 0
        start_date = None
        end_date = None

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

            df = download_func(symbol)

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

            if latest_date_dt is not None:
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
            # 8. 写入失败日志
            # =========================

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

        self._update_price_data(
            symbol=build_us_symbol(ticker),
            download_func=download_us_market_data,
            asset_type="US_STOCK",
            data_source="stooq",
        )

    def update_us_etf(self, ticker):
        """更新单只美国 ETF 行情。"""

        self._update_price_data(
            symbol=build_us_symbol(ticker),
            download_func=download_us_market_data,
            asset_type="US_ETF",
            data_source="stooq",
        )

    def update_us_index(self, symbol):
        """更新单个 Stooq 美国/全球指数行情。"""

        self._update_price_data(
            symbol=build_stooq_internal_symbol(symbol),
            download_func=download_stooq_data,
            asset_type="US_INDEX",
            data_source="stooq",
        )

    def update_us_market_indicator(self, symbol):
        """更新单个 Cboe 市场风险指标。"""

        self._update_price_data(
            symbol=build_cboe_index_internal_symbol(symbol),
            download_func=download_cboe_index_data,
            asset_type="US_MARKET_INDICATOR",
            data_source="cboe",
        )
