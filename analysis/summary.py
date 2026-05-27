"""从 SQLite 数据库读取最近几天的技术指标，并打印成摘要表。

这个脚本主要用于快速查看每个 ETF / 股票最近的技术指标状态。

数据来源：
1. price_data 表：保存原始行情数据，例如 close
2. indicators 表：保存已经计算好的技术指标
"""

import pandas as pd

from database.db_utils import get_connection


# =========================
# 读取数据库中的所有 symbol
# =========================

def get_all_symbols():

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    # 从 indicators 表中找出所有已经计算过指标的 symbol。
    df = pd.read_sql("""
        SELECT DISTINCT symbol
        FROM indicators
        ORDER BY symbol
    """, conn)

    conn.close()

    # 转成普通 Python 列表，方便后面循环。
    return df["symbol"].tolist()


# =========================
# 读取单个 symbol 的摘要数据
# =========================

def load_summary_data(symbol):

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    # 从 indicators 表读取技术指标。
    # 同时 JOIN price_data 表读取 close 收盘价。
    #
    # JOIN 条件：
    # symbol 和 date 都相同。
    #
    # ORDER BY i.date DESC：
    # 先按日期从新到旧排序。
    #
    # LIMIT 5：
    # 只读取最近 5 个交易日。
    df = pd.read_sql("""
        SELECT
            i.date,
            p.close,

            i.VOL5,
            i.VOL20,

            i.MA20,
            i.MA60,

            i.BOLL_UPPER,
            i.BOLL_LOWER,

            i.K,
            i.D,
            i.J,

            i.CCI

        FROM indicators AS i

        JOIN price_data AS p
        ON i.symbol = p.symbol
        AND i.date = p.date

        WHERE i.symbol = ?

        ORDER BY i.date DESC

        LIMIT 5
    """, conn, params=(symbol,))

    conn.close()

    return df


# =========================
# 输出单个 ETF / 股票摘要
# =========================

def print_summary(symbol):

    print("\n")
    print("=" * 80)
    print(f"{symbol} 最近5个交易日技术指标")
    print("=" * 80)

    # 从 SQLite 读取最近 5 天数据。
    recent = load_summary_data(symbol)

    # 如果没有数据，直接提示并返回。
    if recent.empty:
        print(f"{symbol} 没有指标数据，请先运行 indicator.py")
        return

    # 把字符串日期转为 datetime，方便格式化。
    recent["date"] = pd.to_datetime(recent["date"])

    # 因为 SQL 已经 ORDER BY date DESC，
    # 所以这里默认最新日期在最上面。
    #
    # 如果你想按从旧到新显示，可以取消下一行注释：
    # recent = recent.sort_values("date")

    # 只展示最关心的列，避免终端输出太宽。
    columns = [
        "date",
        "close",
        "VOL5",
        "VOL20",
        "MA20",
        "MA60",
        "BOLL_UPPER",
        "BOLL_LOWER",
        "K",
        "D",
        "J",
        "CCI"
    ]

    # 选择需要显示的列。
    recent = recent[columns]

    # 日期格式化为 YYYY-MM-DD，输出更清晰。
    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")

    # round(2) 对数值列保留两位小数。
    recent = recent.round(2)

    # to_string(index=False) 打印表格时隐藏 pandas 自动行号。
    print(recent.to_string(index=False))


# =========================
# 批量输出所有 symbol 摘要
# =========================

def run_summary():

    # 从数据库中自动发现所有已经计算指标的 symbol。
    symbols = get_all_symbols()

    if not symbols:
        print("indicators 表中没有数据，请先运行 analysis.indicator")
        return

    for symbol in symbols:

        try:

            print_summary(symbol)

        except Exception as e:

            # 单个 symbol 出错时只打印错误，不影响其他 symbol 继续输出。
            print(f"{symbol} 输出失败: {e}")


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    run_summary()