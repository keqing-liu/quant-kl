import pandas as pd
import numpy as np
from pathlib import Path

# =========================
# 参数
# =========================

INITIAL_CAPITAL = 100000

FEE_RATE = 0.0001

START_DATE = "2020-01-01"

STOCK_SYMBOL = "sh510310"

BOND_SYMBOL = "sh511010"

# =========================
# 读取数据
# =========================

data_dir = Path("data")

stock_df = pd.read_csv(
    data_dir / f"{STOCK_SYMBOL}_indicators.csv"
)

bond_df = pd.read_csv(
    data_dir / f"{BOND_SYMBOL}_indicators.csv"
)

# 日期
stock_df["date"] = pd.to_datetime(stock_df["date"])
bond_df["date"] = pd.to_datetime(bond_df["date"])

# 排序
stock_df = stock_df.sort_values("date")
bond_df = bond_df.sort_values("date")

# 合并数据
df = pd.merge(
    stock_df,
    bond_df[["date", "close"]],
    on="date",
    suffixes=("_stock", "_bond")
)

# 起始日期过滤
df = df[df["date"] >= START_DATE].copy()

df = df.reset_index(drop=True)

# =========================
# 计算 Score
# =========================

df["Score"] = 0

df.loc[
    df["close_stock"] > df["MA50"],
    "Score"
] += 1

df.loc[
    df["VOLATILITY20"]
    <=
    df["VOLATILITY252"],
    "Score"
] += 1

# =========================
# 回测
# =========================

cash = INITIAL_CAPITAL

position = None

shares = 0

portfolio_values = []

trade_count = 0

for i in range(len(df)):

    row = df.iloc[i]

    date = row["date"]

    stock_price = row["close_stock"]

    bond_price = row["close_bond"]

    score = row["Score"]

    # =====================
    # 目标资产
    # =====================

    if score == 2:
        target_asset = "stock"
        target_price = stock_price
    else:
        target_asset = "bond"
        target_price = bond_price

    # =====================
    # 如果需要换仓
    # =====================

    if position != target_asset:

        # 先卖出
        if position is not None:

            sell_value = shares * current_price

            fee = sell_value * FEE_RATE

            cash = sell_value - fee

            trade_count += 1

        # 再买入
        fee = cash * FEE_RATE

        invest_amount = cash - fee

        shares = invest_amount / target_price

        cash = 0

        position = target_asset

        current_price = target_price

        trade_count += 1

    else:

        current_price = target_price

    # =====================
    # 每日资产价值
    # =====================

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

# 最终资产
final_value = result_df.iloc[-1]["portfolio_value"]

# =========================
# CAGR
# =========================

days = (
    result_df.iloc[-1]["date"]
    -
    result_df.iloc[0]["date"]
).days

years = days / 365.25

cagr = (
    final_value / INITIAL_CAPITAL
) ** (1 / years) - 1

# =========================
# 最大回撤
# =========================

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
# Benchmark: Buy & Hold 股票ETF
# =========================

# 初始买入（扣手续费）
benchmark_invest_amount = (
    INITIAL_CAPITAL
    * (1 - FEE_RATE)
)

benchmark_shares = (
    benchmark_invest_amount
    / df.iloc[0]["close_stock"]
)

# 每日净值
df["benchmark_value"] = (
    benchmark_shares
    * df["close_stock"]
)

# Benchmark最终资产
benchmark_final_value = (
    df.iloc[-1]["benchmark_value"]
)

# =========================
# Benchmark CAGR
# =========================

benchmark_cagr = (
    benchmark_final_value
    / INITIAL_CAPITAL
) ** (1 / years) - 1

# =========================
# Benchmark 最大回撤
# =========================

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