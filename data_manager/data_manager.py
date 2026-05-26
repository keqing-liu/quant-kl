"""数据管理层：把下载到的行情增量写入 SQLite。"""

import pandas as pd

from database.db_utils import (
    get_connection,
    get_latest_date
)

from data_fetch.fetch_etf import download_etf_data
from data_fetch.fetch_stock import download_stock_data


class DataManager:

    def _update_price_data(self, symbol, download_func):

        latest_date = get_latest_date(symbol)

        if latest_date is not None:
            latest_date = pd.to_datetime(latest_date)

        print(f"{symbol} 最新日期: {latest_date}")

        df = download_func(symbol)

        df["date"] = pd.to_datetime(df["date"])

        if latest_date is not None:
            df = df[df["date"] > latest_date]

        if df.empty:
            print(f"{symbol} 无需更新")
            return

        df["symbol"] = symbol

        df = df[[
            "symbol",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume"
        ]]

        # 去掉下载结果内部的重复日期
        df = df.drop_duplicates(
            subset=["symbol", "date"]
        )

        # 如果你的数据库 date 是 TEXT，写入前建议转成字符串
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

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

        conn.commit()
        conn.close()

        print(f"{symbol} 更新 {len(df)} 条数据")

    def update_etf(self, symbol):

        self._update_price_data(
            symbol=symbol,
            download_func=download_etf_data
        )

    def update_stock(self, symbol):

        self._update_price_data(
            symbol=symbol,
            download_func=download_stock_data
        )