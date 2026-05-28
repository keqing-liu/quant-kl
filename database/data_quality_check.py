"""数据质量检查脚本。

运行方式：

    python -m database.data_quality_check

作用：
1. 检查 price_data 是否有重复交易日；
2. 检查 OHLC 价格是否异常；
3. 检查 close 是否缺失或小于等于 0；
4. 检查 volume 是否缺失或小于 0；
5. 检查每个 symbol 的最新日期。
"""

import pandas as pd

from database.db_utils import get_connection, initialize_database


def run_query(title, sql):
    """运行 SQL 检查，并打印结果。"""

    conn = get_connection()
    df = pd.read_sql(sql, conn)
    conn.close()

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

    if df.empty:
        print("未发现问题")
    else:
        print(df)

    return df


def check_duplicate_dates():
    """检查同一 symbol 同一 date 是否有重复记录。"""

    sql = """
    SELECT
        symbol,
        date,
        COUNT(*) AS count
    FROM price_data
    GROUP BY symbol, date
    HAVING COUNT(*) > 1
    ORDER BY symbol, date;
    """

    return run_query("检查 1：重复交易日", sql)


def check_invalid_close():
    """检查 close 是否缺失或小于等于 0。"""

    sql = """
    SELECT
        symbol,
        date,
        close
    FROM price_data
    WHERE close IS NULL OR close <= 0
    ORDER BY symbol, date;
    """

    return run_query("检查 2：close 缺失或小于等于 0", sql)


def check_invalid_ohlc():
    """检查 OHLC 逻辑是否异常。"""

    sql = """
    SELECT
        symbol,
        date,
        open,
        high,
        low,
        close
    FROM price_data
    WHERE
        high < low
        OR close > high
        OR close < low
        OR open > high
        OR open < low
    ORDER BY symbol, date;
    """

    return run_query("检查 3：OHLC 价格逻辑异常", sql)


def check_invalid_volume():
    """检查 volume 是否缺失或小于 0。"""

    sql = """
    SELECT
        symbol,
        date,
        volume
    FROM price_data
    WHERE volume IS NULL OR volume < 0
    ORDER BY symbol, date;
    """

    return run_query("检查 4：volume 缺失或小于 0", sql)


def check_latest_dates():
    """查看每个 symbol 的最新日期。"""

    sql = """
    SELECT
        symbol,
        COUNT(*) AS rows_count,
        MIN(date) AS first_date,
        MAX(date) AS latest_date
    FROM price_data
    GROUP BY symbol
    ORDER BY latest_date ASC, symbol;
    """

    return run_query("检查 5：每个 symbol 的数据区间和最新日期", sql)


def run_data_quality_check():
    """运行全部数据质量检查。"""

    initialize_database()

    check_duplicate_dates()
    check_invalid_close()
    check_invalid_ohlc()
    check_invalid_volume()
    check_latest_dates()

    print("\n数据质量检查完成")


if __name__ == "__main__":
    run_data_quality_check()