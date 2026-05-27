"""计算国债 ETF 最近10年每个自然年的年度收益率。

数据来源：
- quant.db
- price_data 表

计算方法：
每年收益率 = 当年最后一个交易日 close / 当年第一个交易日 close - 1
"""

import pandas as pd

from database.db_utils import get_connection


# =========================
# 参数设置
# =========================

BOND_ETFS = [
    "sh511010",
    "sh511260",
    "sh510310",  # 沪深300
    "sh512100",  # 中证1000
]

YEARS = 10


# =========================
# 读取单个 ETF 的价格数据
# =========================

def load_price_data(symbol):

    conn = get_connection()

    df = pd.read_sql("""
        SELECT
            symbol,
            date,
            close

        FROM price_data

        WHERE symbol = ?

        ORDER BY date
    """, conn, params=(symbol,))

    conn.close()

    return df


# =========================
# 计算单个 ETF 的年度收益
# =========================

def calculate_yearly_return(symbol):

    df = load_price_data(symbol)

    if df.empty:
        print(f"{symbol} 没有价格数据")
        return pd.DataFrame()

    # SQLite 中 date 通常是字符串，转成 datetime 方便提取年份。
    df["date"] = pd.to_datetime(df["date"])

    # 提取自然年份。
    df["year"] = df["date"].dt.year

    # 最近10个自然年。
    latest_year = df["year"].max()
    start_year = latest_year - YEARS + 1

    df = df[df["year"] >= start_year]

    results = []

    # groupby("year")：按自然年分组。
    for year, group in df.groupby("year"):

        # 按日期排序，确保第一行和最后一行正确。
        group = group.sort_values("date")

        first_close = group.iloc[0]["close"]
        last_close = group.iloc[-1]["close"]

        yearly_return = last_close / first_close - 1

        results.append({
            "Year": year,
            "ETF": symbol,
            "Start_Close": first_close,
            "End_Close": last_close,
            "Return": yearly_return
        })

    return pd.DataFrame(results)


# =========================
# 批量计算多个 ETF
# =========================

def run_bond_etf_yearly_return():

    all_results = []

    for symbol in BOND_ETFS:

        result = calculate_yearly_return(symbol)

        if not result.empty:
            all_results.append(result)

    if not all_results:
        print("没有可输出的数据")
        return

    result_df = pd.concat(all_results, ignore_index=True)

    # 转成宽表：年份为行，ETF 为列。
    table = result_df.pivot(
        index="Year",
        columns="ETF",
        values="Return"
    )

    # 按年份从新到旧排列。
    table = table.sort_index(ascending=False)

    # 收益率转成百分比，并保留两位小数。
    table = table * 100
    table = table.round(2)

    # =========================
    # 计算平均年度收益率
    # =========================

    # mean() 默认按列求平均。
    # loc["Average"] 会新增一行。
    table.loc["Average"] = table.mean().round(2)

    print("\n")
    print("=" * 80)
    print("最近10年国债 ETF 自然年度收益率（%）")
    print("=" * 80)

    print(table.to_string())

    print("=" * 80)


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    run_bond_etf_yearly_return()