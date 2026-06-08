"""沪深300 ETF 超跌反弹策略回测。

买入条件：
1. KDJ 中的 K < 20
2. KDJ 中的 J < 0
3. 当日最低价低于布林带下限
4. CCI < -100
5. 20 日均线高于 60 日均线

卖出条件：
1. 持仓收益达到 10% 时止盈
2. 持仓亏损达到 5% 时止损
3. 如果没有触发止盈或止损，则继续持有

数据来源：
1. price_data 表：读取沪深300 ETF 的 OHLC
2. indicators 表：读取 MA20、MA60、BOLL_LOWER、K、J、CCI
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

TAKE_PROFIT_RATE = 0.10

STOP_LOSS_RATE = 0.05


# =========================
# 从 SQLite 读取回测数据
# =========================

def load_backtest_data(stock_symbol):

    conn = get_connection()

    df = pd.read_sql("""
        SELECT
            p.date,
            p.open,
            p.high,
            p.low,
            p.close,

            i.MA20,
            i.MA60,
            i.BOLL_LOWER,
            i.K,
            i.J,
            i.CCI

        FROM price_data AS p

        JOIN indicators AS i
        ON p.symbol = i.symbol
        AND p.date = i.date

        WHERE p.symbol = ?

        ORDER BY p.date
    """, conn, params=(stock_symbol,))

    conn.close()

    return df


def is_buy_signal(row):

    return (
        row["K"] < 20
        and row["J"] < 0
        and row["low"] < row["BOLL_LOWER"]
        and row["CCI"] < -100
        and row["MA20"] > row["MA60"]
    )


# =========================
# 回测函数
# =========================

def run_backtest():

    df = load_backtest_data(STOCK_SYMBOL)

    if df.empty:
        print("没有读取到回测数据，请先确认 price_data 和 indicators 表是否完整")
        return

    df["date"] = pd.to_datetime(df["date"])

    df = df[df["date"] >= START_DATE].copy()

    df = df.reset_index(drop=True)

    df = df.dropna(
        subset=[
            "open",
            "high",
            "low",
            "close",
            "MA20",
            "MA60",
            "BOLL_LOWER",
            "K",
            "J",
            "CCI"
        ]
    ).reset_index(drop=True)

    if df.empty:
        print(f"{START_DATE} 之后没有可用数据")
        return

    # =========================
    # 回测
    # =========================

    cash = INITIAL_CAPITAL

    shares = 0

    position = False

    entry_date = None

    entry_price = None

    portfolio_values = []

    trades = []

    buy_count = 0

    sell_count = 0

    for i in range(len(df)):

        row = df.iloc[i]

        date = row["date"]

        close_price = row["close"]

        if position:

            take_profit_price = entry_price * (
                1 + TAKE_PROFIT_RATE
            )

            stop_loss_price = entry_price * (
                1 - STOP_LOSS_RATE
            )

            sell_reason = None

            sell_price = None

            # 同一天同时触发止盈和止损时，按更保守的止损处理。
            if row["low"] <= stop_loss_price:
                sell_reason = "stop_loss"
                sell_price = stop_loss_price

            elif row["high"] >= take_profit_price:
                sell_reason = "take_profit"
                sell_price = take_profit_price

            if sell_reason is not None:

                sell_value = shares * sell_price

                fee = sell_value * FEE_RATE

                cash = sell_value - fee

                sell_count += 1

                net_return = (
                    cash
                    /
                    trades[-1]["buy_cash_after_fee"]
                    - 1
                )

                trades[-1].update({
                    "sell_date": date,
                    "sell_price": sell_price,
                    "sell_reason": sell_reason,
                    "net_return": net_return,
                    "is_win": net_return > 0
                })

                shares = 0

                position = False

                entry_date = None

                entry_price = None

        if not position and is_buy_signal(row):

            fee = cash * FEE_RATE

            invest_amount = cash - fee

            shares = invest_amount / close_price

            trades.append({
                "buy_date": date,
                "buy_price": close_price,
                "buy_cash_after_fee": invest_amount,
                "sell_date": None,
                "sell_price": None,
                "sell_reason": None,
                "net_return": None,
                "is_win": None
            })

            cash = 0

            position = True

            entry_date = date

            entry_price = close_price

            buy_count += 1

        if position:
            portfolio_value = shares * close_price
        else:
            portfolio_value = cash

        portfolio_values.append({
            "date": date,
            "portfolio_value": portfolio_value,
            "position": "stock" if position else "cash",
            "entry_date": entry_date,
            "entry_price": entry_price
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

    completed_trades = [
        trade
        for trade in trades
        if trade["sell_date"] is not None
    ]

    win_count = sum(
        1
        for trade in completed_trades
        if trade["is_win"]
    )

    win_rate = (
        win_count / len(completed_trades)
        if completed_trades
        else 0
    )

    open_position_count = (
        1
        if position
        else 0
    )

    # =========================
    # Benchmark: Buy & Hold 沪深300 ETF
    # =========================

    benchmark_invest_amount = (
        INITIAL_CAPITAL
        * (1 - FEE_RATE)
    )

    benchmark_shares = (
        benchmark_invest_amount
        /
        df.iloc[0]["close"]
    )

    df["benchmark_value"] = (
        benchmark_shares
        *
        df["close"]
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
    print("沪深300 ETF 超跌反弹策略回测")
    print("=" * 120)

    print(f"开始日期: {START_DATE}")
    print(
        "买入条件: "
        "K < 20 且 J < 0 且 low < BOLL_LOWER "
        "且 CCI < -100 且 MA20 > MA60"
    )
    print(f"止盈: {TAKE_PROFIT_RATE:.0%}")
    print(f"止损: {STOP_LOSS_RATE:.0%}")

    print("\n")
    print("【超跌反弹策略】")
    print("-" * 60)

    print(f"初始资金: {INITIAL_CAPITAL:,.2f}")
    print(f"最终资产: {final_value:,.2f}")
    print(f"累计收益率: {(final_value / INITIAL_CAPITAL - 1):.2%}")
    print(f"年化收益率 CAGR: {cagr:.2%}")
    print(f"最大回撤: {max_drawdown:.2%}")
    print(f"买入次数: {buy_count}")
    print(f"卖出次数: {sell_count}")
    print(f"完成交易次数: {len(completed_trades)}")
    print(f"胜率: {win_rate:.2%}")
    print(f"期末仍持仓笔数: {open_position_count}")

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
