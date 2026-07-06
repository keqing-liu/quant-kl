"""price_data 表读写。

这一层对应分层里的 repository：
只处理 SQLite 的查询和写入，不调用外部数据接口，也不决定业务流程。
"""

from database.db_utils import get_connection


PRICE_DATA_COLUMNS = [
    "symbol",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def get_latest_price_date(symbol):
    """查询某个标的在 price_data 表中的最新日期。"""

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT MAX(date)
            FROM price_data
            WHERE symbol = ?
            """,
            (symbol,),
        )
        result = cursor.fetchone()
    finally:
        conn.close()

    return result[0]


def insert_price_data(price_df):
    """把整理好的行情写入 price_data，返回实际插入行数。"""

    if price_df is None or price_df.empty:
        return 0

    conn = get_connection()
    try:
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
            price_df[PRICE_DATA_COLUMNS].itertuples(index=False, name=None)
        )
        cursor.executemany(sql, data)
        rows_inserted = cursor.rowcount
        conn.commit()
    finally:
        conn.close()

    return rows_inserted
