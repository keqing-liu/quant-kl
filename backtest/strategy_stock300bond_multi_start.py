"""沪深300 ETF 与债券 ETF 的动态轮动回测：多起始年份测试。

测试内容：
分别从 2011 年、2012 年、...、2023 年开始回测到最新数据日期。

比较对象：
1. 动态轮动策略
2. 同期 Buy & Hold 沪深300 ETF
"""

import pandas as pd

from database.db_utils import get_connection


# =========================
# 参数
# =========================

INITIAL_CAPITAL = 100000

FEE_RATE = 0.0001

STOCK_SYMBOL = "sh510310"

BOND_SYMBOL = "sh511010"

START_YEARS = range(2013, 2024)


# =========================
# 从 SQLite 读取回测数据
# =========================

def load_backtest_data(stock_symbol, bond_symbol):

    conn = get_connection()

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
# 单一起始日期回测
# =========================

def run_single_backtest(full_df, start_date):

    df = full_df[full_df["date"] >= start_date].copy()

    df = df.reset_index(drop=True)

    if df.empty or len(df) < 2:
        return None

    # =========================
    # 计算 Score
    # =========================

    df["Score"] = 0

    # 条件 1：
    # 股票 ETF 收盘价高于 MA50，代表中期趋势较强。
    df.loc[
        df["close_stock"] > df["MA50"],
        "Score"
    ] += 1

    # 条件 2：
    # 20 日波动率不高于 252 日波动率，代表近期风险没有明显放大。
    df.loc[
        df["VOLATILITY20"] <= df["VOLATILITY252"],
        "Score"
    ] += 1

    # =========================
    # 动态轮动策略回测
    # =========================

    cash = INITIAL_CAPITAL
    position = None
    shares = 0
    current_price = None
    trade_count = 0

    portfolio_values = []

    for i in range(len(df)):

        row = df.iloc[i]

        date = row["date"]
        stock_price = row["close_stock"]
        bond_price = row["close_bond"]
        score = row["Score"]

        # score == 2 时持有股票 ETF；
        # 否则持有债券 ETF。
        if score == 2:
            target_asset = "stock"
            target_price = stock_price
        else:
            target_asset = "bond"
            target_price = bond_price

        # 如果目标资产和当前持仓不同，则换仓。
        if position != target_asset:

            # 先卖出原持仓。
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

            # 不换仓时，只更新当前资产价格。
            current_price = target_price

        portfolio_value = shares * current_price

        portfolio_values.append({
            "date": date,
            "portfolio_value": portfolio_value
        })

    result_df = pd.DataFrame(portfolio_values)

    strategy_final_value = result_df.iloc[-1]["portfolio_value"]

    strategy_total_return = (
        strategy_final_value / INITIAL_CAPITAL - 1
    )

    # =========================
    # 策略最大回撤
    # =========================

    result_df["rolling_max"] = (
        result_df["portfolio_value"]
        .cummax()
    )

    result_df["drawdown"] = (
        result_df["portfolio_value"]
        / result_df["rolling_max"]
        - 1
    )

    strategy_max_drawdown = result_df["drawdown"].min()

    # =========================
    # 策略 CAGR
    # =========================

    days = (
        result_df.iloc[-1]["date"]
        -
        result_df.iloc[0]["date"]
    ).days

    years = days / 365.25

    strategy_cagr = (
        strategy_final_value / INITIAL_CAPITAL
    ) ** (1 / years) - 1

    # =========================
    # Benchmark：Buy & Hold 沪深300 ETF
    # =========================

    benchmark_invest_amount = (
        INITIAL_CAPITAL
        * (1 - FEE_RATE)
    )

    benchmark_shares = (
        benchmark_invest_amount
        / df.iloc[0]["close_stock"]
    )

    df["benchmark_value"] = (
        benchmark_shares
        * df["close_stock"]
    )

    benchmark_final_value = df.iloc[-1]["benchmark_value"]

    benchmark_total_return = (
        benchmark_final_value / INITIAL_CAPITAL - 1
    )

    benchmark_cagr = (
        benchmark_final_value / INITIAL_CAPITAL
    ) ** (1 / years) - 1

    df["benchmark_rolling_max"] = (
        df["benchmark_value"]
        .cummax()
    )

    df["benchmark_drawdown"] = (
        df["benchmark_value"]
        / df["benchmark_rolling_max"]
        - 1
    )

    benchmark_max_drawdown = (
        df["benchmark_drawdown"]
        .min()
    )

    return {
        "Start_Date": start_date.strftime("%Y-%m-%d"),
        "End_Date": df.iloc[-1]["date"].strftime("%Y-%m-%d"),

        "Strategy_Final": strategy_final_value,
        "Strategy_Return": strategy_total_return,
        "Strategy_CAGR": strategy_cagr,
        "Strategy_MaxDD": strategy_max_drawdown,

        "Benchmark_Final": benchmark_final_value,
        "Benchmark_Return": benchmark_total_return,
        "Benchmark_CAGR": benchmark_cagr,
        "Benchmark_MaxDD": benchmark_max_drawdown,

        "Excess_Return": strategy_total_return - benchmark_total_return,
        "Trade_Count": trade_count
    }


# =========================
# 多起始年份回测
# =========================

def run_multi_start_backtest():

    full_df = load_backtest_data(
        STOCK_SYMBOL,
        BOND_SYMBOL
    )

    if full_df.empty:
        print("没有读取到回测数据，请先确认 price_data 和 indicators 表是否完整")
        return

    full_df["date"] = pd.to_datetime(full_df["date"])

    results = []

    for year in START_YEARS:

        start_date = pd.to_datetime(f"{year}-01-01")

        result = run_single_backtest(
            full_df,
            start_date
        )

        if result is not None:
            results.append(result)

    result_df = pd.DataFrame(results)

    if result_df.empty:
        print("没有可输出的回测结果")
        return

    # =========================
    # 格式化输出
    # =========================

        # =========================
    # 只保留年化收益率比较
    # =========================

    output_df = result_df[[
        "Start_Date",
        "End_Date",
        "Strategy_CAGR",
        "Benchmark_CAGR",
        "Excess_Return",
        "Trade_Count"
    ]].copy()

    # 转成百分比
    percent_columns = [
        "Strategy_CAGR",
        "Benchmark_CAGR",
        "Excess_Return"
    ]

    for col in percent_columns:
        output_df[col] = (
            output_df[col] * 100
        ).round(2)

    print("\n")
    print("=" * 160)
    print("动态轮动策略 vs Buy & Hold 沪深300 ETF：不同起始年份回测")
    print("=" * 160)

    print(output_df.to_string(index=False))

    print("=" * 160)


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    run_multi_start_backtest()