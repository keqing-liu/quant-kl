"""股债轮动信号：用简单规则判断股票ETF是否值得关注。

数据来源：
1. price_data 表：读取 close 收盘价
2. indicators 表：读取 MA50、VOLATILITY20、VOLATILITY252 等技术指标
"""

import pandas as pd

from database.db_utils import get_connection


# =========================
# 读取某个标的最近5日指标
# =========================

def load_recent_indicators(symbol):

    conn = get_connection()

    df = pd.read_sql("""
        SELECT
            i.symbol,
            i.date,

            p.close,

            i.MA50,
            i.VOLATILITY20,
            i.VOLATILITY252

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
# 判断 ETF 值得关注的打分系统
# =========================

def check_signal(symbol):

    # 从 SQLite 读取最近5日数据。
    df = load_recent_indicators(symbol)

    if df.empty:
        raise ValueError(
            f"{symbol} 没有指标数据，请先运行 indicator.py"
        )

    signals = []

    # iterrows():
    # 逐行遍历 DataFrame。
    for _, row in df.iterrows():

        score = 0

        # =========================
        # 打分规则 1：趋势条件
        # =========================

        # 收盘价高于 MA50：
        # 表示价格位于中期趋势线上方。
        if row["close"] > row["MA50"]:
            score += 1

        # =========================
        # 打分规则 2：风险条件
        # =========================

        # 近期波动率不高于长期波动率：
        # 表示近期市场相对稳定。
        if row["VOLATILITY20"] <= row["VOLATILITY252"]:
            score += 1

        # =========================
        # 保存结果
        # =========================

        signals.append({

            "ETF": symbol,

            "Date": pd.to_datetime(
                row["date"]
            ).strftime("%Y-%m-%d"),

            "Close": round(row["close"], 2),

            "MA50": round(row["MA50"], 2),

            "VOLATILITY20": round(
                row["VOLATILITY20"], 6
            ),

            "VOLATILITY252": round(
                row["VOLATILITY252"], 6
            ),

            "Score": score

        })

    return signals


# =========================
# 批量运行打分
# =========================

def run_signal_check(target_symbols):

    all_signals = []

    for symbol in target_symbols:

        try:

            results = check_signal(symbol)

            # extend:
            # 把列表里的多个结果加入总列表。
            all_signals.extend(results)

        except Exception as e:

            print(f"{symbol} 分析失败: {e}")

    print("\n")
    print("=" * 120)
    print("ETF 技术指标打分（最近5个交易日）")
    print("=" * 120)

    signal_df = pd.DataFrame(all_signals)

    if signal_df.empty:

        print("没有可输出的信号结果")
        print("=" * 120)

        return

    # 日期从最新到最旧排列。
    signal_df = signal_df.sort_values(
        ["ETF", "Date"],
        ascending=[True, False]
    )

    print(signal_df.to_string(index=False))

    print("=" * 120)


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    target_symbols = [
        "sh510310"
    ]

    run_signal_check(target_symbols)