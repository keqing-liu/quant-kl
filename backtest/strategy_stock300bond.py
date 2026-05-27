"""沪深300 ETF 与债券 ETF 的动态轮动回测。

策略思想：
用股票 ETF 的趋势和波动率打分；
分数高时持有股票 ETF，否则切换到债券 ETF。

数据来源：
1. price_data 表：读取股票 ETF 和债券 ETF 的 close
2. indicators 表：读取股票 ETF 的 MA50、VOLATILITY20、VOLATILITY252
"""

import pandas as pd

from database.db_utils import get_connection


# =========================
# 参数
# =========================

INITIAL_CAPITAL = 100000

FEE_RATE = 0.0001

START_DATE = "2021-01-01"

STOCK_SYMBOL = "sh510310"

BOND_SYMBOL = "sh511010"


# =========================
# 从 SQLite 读取回测数据
# =========================

def load_backtest_data(stock_symbol, bond_symbol):

    conn = get_connection()

    # 说明：
    # stock_i 是股票 ETF 的技术指标表
    # stock_p 是股票 ETF 的价格表
    # bond_p 是债券 ETF 的价格表
    #
    # 回测需要：
    # 1. 股票 ETF close
    # 2. 股票 ETF MA50 / VOLATILITY20 / VOLATILITY252
    # 3. 债券 ETF close
    #
    # 用 date 连接股票和债券数据，只保留两者都有行情的日期。
    df = pd.read_sql("""
        SELECT
            stock_i.date,

            stock_p.close AS close_stock,
            bond_p.close AS close_bond,

            stock_i.MA50,
            stock_i.VOLATILITY20,
            stock_i.VOLATILITY252

        FROM indicators AS stock_i

        JOIN price_data AS stock_p
        ON stock_i.symbol = stock_p.symbol
        AND stock_i.date = stock_p.date

        JOIN price_data AS bond_p
        ON stock_i.date = bond_p.date

        WHERE stock_i.symbol = ?
        AND stock_p.symbol = ?
        AND bond_p.symbol = ?

        ORDER BY stock_i.date
    """, conn, params=(stock_symbol, stock_symbol, bond_symbol))

    conn.close()

    return df


# =========================
# 回测函数
# =========================

def run_backtest():

    # 从 SQLite 读取数据。
    df = load_backtest_data(
        STOCK_SYMBOL,
        BOND_SYMBOL
    )

    if df.empty:
        print("没有读取到回测数据，请先确认 price_data 和 indicators 表是否完整")
        return

    # 日期转换，便于过滤和计算年数。
    df["date"] = pd.to_datetime(df["date"])

    # 只保留 START_DATE 之后的数据。
    df = df[df["date"] >= START_DATE].copy()

    # 重置行号，便于后面按顺序遍历。
    df = df.reset_index(drop=True)

    if df.empty:
        print(f"{START_DATE} 之后没有可用数据")
        return

    # =========================
    # 计算 Score
    # =========================

    df["Score"] = 0

    # 条件 1：
    # 股票 ETF 收盘价高于 50 日均线，说明中期趋势较强。
    df.loc[
        df["close_stock"] > df["MA50"],
        "Score"
    ] += 1

    # 条件 2：
    # 近期波动率不高于长期波动率，说明近期风险没有明显放大。
    df.loc[
        df["VOLATILITY20"] <= df["VOLATILITY252"],
        "Score"
    ] += 1

    # =========================
    # 回测
    # =========================

    cash = INITIAL_CAPITAL

    position = None

    shares = 0

    current_price = None

    portfolio_values = []

    trade_count = 0

    for i in range(len(df)):

        row = df.iloc[i]

        date = row["date"]

        stock_price = row["close_stock"]

        bond_price = row["close_bond"]

        score = row["Score"]

        # 分数满分时持有股票 ETF，否则持有债券 ETF。
        if score == 2:
            target_asset = "stock"
            target_price = stock_price
        else:
            target_asset = "bond"
            target_price = bond_price

        # 如果当前持仓和目标资产不同，就换仓。
        if position != target_asset:

            # 先卖出当前持仓。
            if position is not None:

                sell_value = shares * current_price

                fee = sell_value * FEE_RATE

                cash = sell_value - fee

                trade_count += 1

            # 再买入目标资产。
            fee = cash * FEE_RATE

            invest_amount = cash - fee

            shares = invest_amount / target_price

            cash = 0

            position = target_asset

            current_price = target_price

            trade_count += 1

        else:

            # 不换仓时，只更新当前价格。
            current_price = target_price

        portfolio_value = shares * current_price

        portfolio_values.append({
            "date": date,
            "portfolio_value": portfolio_value,
            "position": position,
            "score": score
        })

    # =========================
    # 回测结果
    # =========================

    result_df = pd.DataFrame(portfolio_values)

    final_value = result_df.iloc[-1]["portfolio_value"]

    days = (
        result_df.iloc[-1]["date"]
        -
        result_df.iloc[0]["date"]
    ).days

    years = days / 365.25

    cagr = (
        final_value / INITIAL_CAPITAL
    ) ** (1 / years) - 1

    result_df["rolling_max"] = (
        result_df["portfolio_value"]
        .cummax()
    )

    result_df["drawdown"] = (
        result_df["portfolio_value"]
        /
        result_df["rolling_max"]
        - 1
    )

    max_drawdown = result_df["drawdown"].min()

    # =========================
    # Benchmark: Buy & Hold 股票 ETF
    # =========================

    benchmark_invest_amount = (
        INITIAL_CAPITAL
        * (1 - FEE_RATE)
    )

    benchmark_shares = (
        benchmark_invest_amount
        /
        df.iloc[0]["close_stock"]
    )

    df["benchmark_value"] = (
        benchmark_shares
        *
        df["close_stock"]
    )

    benchmark_final_value = (
        df.iloc[-1]["benchmark_value"]
    )

    benchmark_cagr = (
        benchmark_final_value
        /
        INITIAL_CAPITAL
    ) ** (1 / years) - 1

    df["benchmark_rolling_max"] = (
        df["benchmark_value"]
        .cummax()
    )

    df["benchmark_drawdown"] = (
        df["benchmark_value"]
        /
        df["benchmark_rolling_max"]
        - 1
    )

    benchmark_max_drawdown = (
        df["benchmark_drawdown"]
        .min()
    )

    # =========================
    # 输出结果
    # =========================

    print("\n")
    print("=" * 120)
    print("ETF 动态轮动策略回测")
    print("=" * 120)

    print(f"开始日期: {START_DATE}")

    print("\n")
    print("【动态轮动策略】")
    print("-" * 60)

    print(f"初始资金: {INITIAL_CAPITAL:,.2f}")
    print(f"最终资产: {final_value:,.2f}")
    print(f"累计收益率: {(final_value / INITIAL_CAPITAL - 1):.2%}")
    print(f"年化收益率 CAGR: {cagr:.2%}")
    print(f"最大回撤: {max_drawdown:.2%}")
    print(f"交易次数: {trade_count}")

    print("\n")
    print("【Buy & Hold 沪深300ETF】")
    print("-" * 60)

    print(f"最终资产: {benchmark_final_value:,.2f}")

    print(
        f"累计收益率: "
        f"{(benchmark_final_value / INITIAL_CAPITAL - 1):.2%}"
    )

    print(f"年化收益率 CAGR: {benchmark_cagr:.2%}")
    print(f"最大回撤: {benchmark_max_drawdown:.2%}")

    print("=" * 120)


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    run_backtest()