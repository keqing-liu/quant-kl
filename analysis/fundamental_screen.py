"""基于财务指标做基本面集中筛选。

筛选规则：
1. 只使用年报数据，即 fiscal_period = 'Q4'；
2. 默认只看近 10 年年报；
3. 要求可得的每一年 ROE 都大于 15%；
4. 输出平均 ROE、平均负债率、平均净利润增长率，并按平均 ROE 从高到低排列。
"""

import argparse
from datetime import date

import pandas as pd

from database.db_utils import get_connection


DEFAULT_ROE_THRESHOLD = 15
DEFAULT_YEARS = 10


def get_default_start_year(years=DEFAULT_YEARS):
    """计算近 N 年筛选的起始年份。"""

    return date.today().year - years


def load_annual_financial_data(start_year=None):
    """从 SQLite 读取年报财务指标数据。"""

    conn = get_connection()

    # 只筛选年报 Q4：
    # 季报 ROE 波动更大，而且不同公司季度口径可能不完全一致。
    # 用年报做第一版基本面筛选，结果更稳定，也更容易解释。
    sql = """
    SELECT
        f.symbol,
        COALESCE(s.name, a.name) AS name,
        f.report_date,
        f.fiscal_year,
        f.roe,
        f.net_profit_yoy,
        f.debt_ratio
    FROM financial_indicators AS f
    LEFT JOIN stock_universe AS s
        ON f.symbol = s.symbol
    LEFT JOIN asset_info AS a
        ON f.symbol = a.symbol
    WHERE f.fiscal_period = 'Q4'
      AND f.roe IS NOT NULL
    """

    params = []

    if start_year is not None:
        sql += " AND f.fiscal_year >= ?"
        params.append(start_year)

    sql += """
    ORDER BY f.symbol, f.fiscal_year
    """

    df = pd.read_sql(sql, conn, params=params)

    conn.close()

    return df


def summarize_annual_financial_data(df):
    """按股票汇总年报财务指标。"""

    if df.empty:
        return pd.DataFrame()

    results = []

    for symbol, group in df.groupby("symbol"):
        group = group.sort_values("fiscal_year")

        # 股票名称优先从 stock_universe 来；如果没有股票池记录，再退回 asset_info。
        name = group["name"].dropna().iloc[-1] if group["name"].notna().any() else None

        years_count = len(group)
        min_roe = group["roe"].min()
        max_roe = group["roe"].max()
        avg_roe = group["roe"].mean()

        results.append(
            {
                "symbol": symbol,
                "name": name,
                "years_count": years_count,
                "min_roe": min_roe,
                "max_roe": max_roe,
                "avg_roe": avg_roe,
                "avg_debt_ratio": group["debt_ratio"].mean(),
                "avg_net_profit_yoy": group["net_profit_yoy"].mean(),
            }
        )

    result_df = pd.DataFrame(results)

    if result_df.empty:
        return result_df

    return result_df.sort_values(
        by="avg_roe",
        ascending=False,
    ).reset_index(drop=True)


def screen_roe_companies(
    roe_threshold=DEFAULT_ROE_THRESHOLD,
    start_year=None,
):
    """筛选近 N 年每年 ROE 都达标的公司。"""

    if start_year is None:
        start_year = get_default_start_year()

    df = load_annual_financial_data(start_year=start_year)
    summary_df = summarize_annual_financial_data(df)

    if summary_df.empty:
        return pd.DataFrame()

    # 这里用 min_roe > threshold，表示可得年份里每一年都必须达标。
    # 注意：当前规则允许上市不足 10 年的公司按可得年份参与筛选。
    return summary_df[
        summary_df["min_roe"] > roe_threshold
    ].sort_values(
        by="avg_roe",
        ascending=False,
    ).reset_index(drop=True)


def format_screen_result(df):
    """整理输出表格中的数值精度。"""

    display_df = df.copy()

    for column in (
        "min_roe",
        "max_roe",
        "avg_roe",
        "avg_debt_ratio",
        "avg_net_profit_yoy",
    ):
        display_df[column] = display_df[column].round(2)

    return display_df


def run_fundamental_screen(
    roe_threshold=DEFAULT_ROE_THRESHOLD,
    start_year=None,
    output=None,
):
    """运行基本面筛选并打印结果。"""

    if start_year is None:
        start_year = get_default_start_year()

    result_df = screen_roe_companies(
        roe_threshold=roe_threshold,
        start_year=start_year,
    )

    print("\n")
    print("=" * 100)
    print(f"近 10 年每一年年报 ROE 都 > {roe_threshold}% 的公司")
    print(f"使用年报年份 >= {start_year}；不足 10 年的公司按可得年份计算")
    print("=" * 100)

    if result_df.empty:
        print("没有筛选出符合条件的公司")
    else:
        print(format_screen_result(result_df).to_string(index=False))
        print(f"\n共筛选出 {len(result_df)} 家公司")

    if output is not None:
        result_df.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"筛选结果已保存到: {output}")

    return result_df


def parse_args():
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="按年报 ROE 筛选基本面较好的公司"
    )
    parser.add_argument(
        "--roe",
        type=float,
        default=DEFAULT_ROE_THRESHOLD,
        help="ROE 阈值，默认 15",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="只使用该年份之后的年报数据；默认近 10 年",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="可选：把筛选结果保存为 CSV",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    run_fundamental_screen(
        roe_threshold=args.roe,
        start_year=args.start_year,
        output=args.output,
    )
