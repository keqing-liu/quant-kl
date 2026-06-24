"""短期超跌评分：用 KDJ、CCI、布林带和均线筛选值得关注的 ETF / 股票。

数据来源：
1. price_data 表：读取 close 等原始行情
2. indicators 表：读取已经计算好的技术指标
"""

import pandas as pd

from config.watchlist import WATCHLIST
from database.db_utils import get_connection
from data_fetch.fetch_cboe_market import build_cboe_index_internal_symbol


SKIP_SIGNAL_SYMBOLS = {
    build_cboe_index_internal_symbol(symbol)
    for symbol in WATCHLIST.get("US_MARKET_INDICATOR", [])
}


# =========================
# 获取所有已经计算指标的 symbol
# =========================

def get_all_symbols():

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    # DISTINCT 表示去重；
    # ORDER BY symbol 让输出更稳定。
    df = pd.read_sql("""
        SELECT DISTINCT symbol
        FROM indicators
        ORDER BY symbol
    """, conn)

    conn.close()

    # 转成普通 Python list。
    return [
        symbol
        for symbol in df["symbol"].tolist()
        if symbol not in SKIP_SIGNAL_SYMBOLS
    ]


# =========================
# 读取某个 symbol 最新一日指标
# =========================

def load_latest_indicator(symbol):

    conn = get_connection()

    # JOIN:
    # indicators 表保存技术指标，
    # price_data 表保存 close 等原始行情。
    #
    # 通过 symbol + date 连接两张表。
    df = pd.read_sql("""

        SELECT

            i.symbol,
            i.date,

            p.close,

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

        LIMIT 1

    """, conn, params=(symbol,))

    conn.close()

    return df


# =========================
# 判断 ETF / 股票值得关注的打分系统
# =========================

def check_signal(symbol):

    # 从数据库读取最新一日指标。
    df = load_latest_indicator(symbol)

    if df.empty:
        raise ValueError(f"{symbol} 没有指标数据")

    # iloc[0]：
    # 因为 SQL 已经 ORDER BY date DESC，
    # 第一行就是最新交易日。
    latest = df.iloc[0]

    # score：
    # 每满足一个条件加 1 分。
    score = 0

    # =========================
    # 打分规则
    # =========================

    # K < 20：
    # KDJ 处于较低位置，
    # 常被视为偏超卖。
    if latest["K"] < 20:
        score += 1

    # J < 0：
    # J 线比 K / D 更敏感，
    # 小于 0 代表短期可能过冷。
    if latest["J"] < 0:
        score += 1

    # CCI < -100：
    # 价格偏离均值较大，
    # 有时意味着超卖。
    if latest["CCI"] < -120:
        score += 1

    # 收盘价接近布林下轨：
    # 常用于寻找短期低位。
    #
    # 1.01：
    # 给一个 1% 容忍区间。
    if latest["close"] <= latest["BOLL_LOWER"] * 1.01:
        score += 1

    # =========================
    # 返回字典
    # =========================

    return {

        "ETF": symbol,

        "Date": pd.to_datetime(
            latest["date"]
        ).strftime("%Y-%m-%d"),

        "Close": round(latest["close"], 2),

        "MA20": round(latest["MA20"], 2),
        "MA60": round(latest["MA60"], 2),

        "BOLL_UPPER": round(
            latest["BOLL_UPPER"], 2
        ),

        "BOLL_LOWER": round(
            latest["BOLL_LOWER"], 2
        ),

        "K": round(latest["K"], 2),
        "D": round(latest["D"], 2),
        "J": round(latest["J"], 2),

        "CCI": round(latest["CCI"], 2),

        "Score": score
    }


# =========================
# 批量运行打分
# =========================

def run_signal_check():

    # 自动获取数据库中的全部 symbol。
    symbols = get_all_symbols()

    signals = []

    for symbol in symbols:

        try:

            result = check_signal(symbol)

            signals.append(result)

        except Exception as e:

            print(f"{symbol} 分析失败: {e}")

    # =========================
    # 输出结果
    # =========================

    print("\n")
    print("=" * 120)
    print("短期超跌评分（分数越高越值得关注）")
    print("=" * 120)

    signal_df = pd.DataFrame(signals)

    # 如果没有结果，直接退出。
    if signal_df.empty:

        print("没有可输出的数据")
        print("=" * 120)

        return

    # Score 越高排越前。
    signal_df = signal_df.sort_values(
        "Score",
        ascending=False
    )

    # 显示完整结果。
    # 如果标的太多，
    # 可以改成：
    #
    # signal_df.head(10)
    #
    print(signal_df.to_string(index=False))

    print("=" * 120)


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    run_signal_check()
