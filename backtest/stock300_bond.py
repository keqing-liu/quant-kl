"""沪深300 ETF 与债券 ETF 的动态轮动回测。

策略思想：用股票 ETF 的趋势和波动率打分；
分数高时持有股票 ETF，否则切换到债券 ETF。
"""

import pandas as pd
import numpy as np
from pathlib import Path

# =========================
# 参数
# =========================

# 初始资金。
INITIAL_CAPITAL = 100000

# 单边交易费率。0.0001 表示万分之一。
FEE_RATE = 0.0001

# 回测起始日期。
START_DATE = "2015-01-01"

# 股票资产：沪深300 ETF。
STOCK_SYMBOL = "sh510310"

# 防守资产：国债 ETF。
BOND_SYMBOL = "sh511010"

# =========================
# 读取数据
# =========================

data_dir = Path("data")

# 读取股票 ETF 指标文件。
stock_df = pd.read_csv(
    data_dir / f"{STOCK_SYMBOL}_indicators.csv"
)

# 读取债券 ETF 指标文件。
bond_df = pd.read_csv(
    data_dir / f"{BOND_SYMBOL}_indicators.csv"
)

# 把日期列转为 datetime，便于合并、过滤和计算年数。
stock_df["date"] = pd.to_datetime(stock_df["date"])
bond_df["date"] = pd.to_datetime(bond_df["date"])

# 按日期排序，保证回测按时间推进。
stock_df = stock_df.sort_values("date")
bond_df = bond_df.sort_values("date")

# 按 date 合并两张表，只保留两个资产都有数据的交易日。
df = pd.merge(
    stock_df,
    bond_df[["date", "close"]],
    on="date",
    suffixes=("_stock", "_bond")
)

# 只保留 START_DATE 之后的数据；copy() 避免 pandas 链式赋值警告。
df = df[df["date"] >= START_DATE].copy()

# 重置行号，便于后面用 iloc[i] 顺序遍历。
df = df.reset_index(drop=True)

# =========================
# 计算 Score
# =========================

# 初始化分数列，默认 0 分。
df["Score"] = 0

# 条件 1：股票 ETF 收盘价高于 50 日均线，说明中期趋势较强。
df.loc[
    df["close_stock"] > df["MA50"],
    "Score"
] += 1

# 条件 2：近期波动率不高于长期波动率，说明近期风险没有明显放大。
df.loc[
    df["VOLATILITY20"]
    <=
    df["VOLATILITY252"],
    "Score"
] += 1

# =========================
# 回测
# =========================

# cash 表示当前现金。刚开始全部是现金。
cash = INITIAL_CAPITAL

# position 表示当前持仓资产：None / "stock" / "bond"。
position = None

# shares 表示当前持有的份额数量。
shares = 0

# 每日组合净值记录。
portfolio_values = []

# 交易次数统计，买入和卖出各算一次。
trade_count = 0

for i in range(len(df)):

    # 当前交易日的一行数据。
    row = df.iloc[i]

    date = row["date"]

    stock_price = row["close_stock"]

    bond_price = row["close_bond"]

    score = row["Score"]

    # =====================
    # 目标资产
    # =====================

    # 分数满分时持有股票 ETF，否则持有债券 ETF。
    if score == 2:
        target_asset = "stock"
        target_price = stock_price
    else:
        target_asset = "bond"
        target_price = bond_price

    # =====================
    # 如果需要换仓
    # =====================

    # 如果当前持仓和目标资产不同，就需要换仓。
    if position != target_asset:

        # 先卖出当前持仓，变成现金。
        if position is not None:

            sell_value = shares * current_price

            fee = sell_value * FEE_RATE

            # 卖出后现金 = 卖出金额 - 手续费。
            cash = sell_value - fee

            trade_count += 1

        # 再用现金买入目标资产。
        fee = cash * FEE_RATE

        invest_amount = cash - fee

        # 买到的份额 = 可投资金额 / 目标资产价格。
        shares = invest_amount / target_price

        cash = 0

        position = target_asset

        current_price = target_price

        trade_count += 1

    else:

        # 不换仓时，只需要用今天的目标资产价格更新市值。
        current_price = target_price

    # =====================
    # 每日资产价值
    # =====================

    # 组合市值 = 持有份额 * 当前价格；本策略换仓后 cash 始终为 0。
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

# 每日净值列表转成 DataFrame，方便后续统计。
result_df = pd.DataFrame(portfolio_values)

# 最终资产取最后一天组合市值。
final_value = result_df.iloc[-1]["portfolio_value"]

# =========================
# CAGR
# =========================

# 回测总天数。
days = (
    result_df.iloc[-1]["date"]
    -
    result_df.iloc[0]["date"]
).days

# 年数用 365.25 近似，考虑闰年。
years = days / 365.25

# CAGR：复合年化收益率。
cagr = (
    final_value / INITIAL_CAPITAL
) ** (1 / years) - 1

# =========================
# 最大回撤
# =========================

# rolling_max 是历史最高净值曲线。
result_df["rolling_max"] = (
    result_df["portfolio_value"]
    .cummax()
)

# drawdown = 当前净值 / 历史最高净值 - 1。
result_df["drawdown"] = (
    result_df["portfolio_value"]
    /
    result_df["rolling_max"]
    - 1
)

# 最大回撤是 drawdown 的最小值，通常是负数。
max_drawdown = result_df["drawdown"].min()


# =========================
# Benchmark: Buy & Hold 股票ETF
# =========================

# 基准：一开始买入股票 ETF 后一直持有。
benchmark_invest_amount = (
    INITIAL_CAPITAL
    * (1 - FEE_RATE)
)

# 基准买入份额。
benchmark_shares = (
    benchmark_invest_amount
    / df.iloc[0]["close_stock"]
)

# 基准每日净值 = 固定份额 * 当日股票 ETF 收盘价。
df["benchmark_value"] = (
    benchmark_shares
    * df["close_stock"]
)

# 基准最终资产。
benchmark_final_value = (
    df.iloc[-1]["benchmark_value"]
)

# =========================
# Benchmark CAGR
# =========================

# 基准 CAGR。
benchmark_cagr = (
    benchmark_final_value
    / INITIAL_CAPITAL
) ** (1 / years) - 1

# =========================
# Benchmark 最大回撤
# =========================

# 基准历史最高净值。
df["benchmark_rolling_max"] = (
    df["benchmark_value"]
    .cummax()
)

# 基准回撤曲线。
df["benchmark_drawdown"] = (
    df["benchmark_value"]
    /
    df["benchmark_rolling_max"]
    - 1
)

# 基准最大回撤。
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
