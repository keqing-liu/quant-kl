"""输出单只股票近 N 年核心财务指标。

默认示例：

    python -m analysis.stock_financial_snapshot

指定股票：

    python -m analysis.stock_financial_snapshot --symbol sh600519 --years 10
"""

import argparse
from datetime import date

import pandas as pd

from database.db_utils import get_connection


DEFAULT_SYMBOL = "sh600519"
DEFAULT_YEARS = 10


def normalize_symbol(symbol):
    """把 6 位代码或带前缀代码统一成 sh/sz 格式。"""

    value = str(symbol).strip().lower()

    if value.startswith(("sh", "sz")):
        return value

    if len(value) == 6 and value.isdigit():
        if value.startswith("6"):
            return f"sh{value}"

        return f"sz{value}"

    raise ValueError(f"无法识别股票代码: {symbol}")


def get_default_start_year(years=DEFAULT_YEARS):
    """计算近 N 年年报的起始年份。"""

    return date.today().year - years


def load_annual_indicator_data(symbol, start_year):
    """读取 financial_indicators 中的年报指标。"""

    conn = get_connection()

    try:
        sql = """
        SELECT
            f.symbol,
            COALESCE(s.name, a.name) AS name,
            f.report_date,
            f.fiscal_year,
            f.roe,
            f.net_profit,
            f.gross_margin,
            f.debt_ratio
        FROM financial_indicators AS f
        LEFT JOIN stock_universe AS s
            ON f.symbol = s.symbol
        LEFT JOIN asset_info AS a
            ON f.symbol = a.symbol
        WHERE f.symbol = ?
          AND f.fiscal_period = 'Q4'
          AND f.fiscal_year >= ?
        ORDER BY f.fiscal_year
        """

        return pd.read_sql(sql, conn, params=[symbol, start_year])

    finally:
        conn.close()


def load_annual_statement_data(symbol, start_year):
    """读取新浪三大报表中用于补充净利润和毛利率的年报科目。"""

    conn = get_connection()

    try:
        sql = """
        SELECT
            symbol,
            report_date,
            statement_type,
            item_name,
            item_value
        FROM financial_statement_items
        WHERE symbol = ?
          AND substr(report_date, 6, 5) = '12-31'
          AND CAST(substr(report_date, 1, 4) AS INTEGER) >= ?
          AND statement_type = '利润表'
          AND item_name IN (
              '营业总收入',
              '营业收入',
              '营业成本',
              '归属于母公司所有者的净利润',
              '净利润'
          )
        ORDER BY report_date
        """

        return pd.read_sql(sql, conn, params=[symbol, start_year])

    finally:
        conn.close()


def build_statement_wide(statement_df):
    """把利润表科目转成每个报告期一行。"""

    if statement_df.empty:
        return pd.DataFrame(
            columns=[
                "report_date",
                "statement_revenue",
                "statement_cost",
                "statement_net_profit",
                "calculated_gross_margin",
            ]
        )

    rows = []

    for report_date, group in statement_df.groupby("report_date"):
        revenue = _first_item(group, ["营业总收入", "营业收入"])
        cost = _first_item(group, ["营业成本"])
        net_profit = _first_item(group, ["归属于母公司所有者的净利润", "净利润"])
        calculated_gross_margin = None

        if revenue is not None and revenue != 0 and cost is not None:
            calculated_gross_margin = (revenue - cost) / revenue * 100

        rows.append(
            {
                "report_date": report_date,
                "statement_revenue": revenue,
                "statement_cost": cost,
                "statement_net_profit": net_profit,
                "calculated_gross_margin": calculated_gross_margin,
            }
        )

    return pd.DataFrame(rows)


def load_stock_financial_snapshot(symbol=DEFAULT_SYMBOL, years=DEFAULT_YEARS):
    """读取并整理单只股票近 N 年 ROE、利润、毛利率、负债率。"""

    symbol = normalize_symbol(symbol)
    start_year = get_default_start_year(years)
    indicator_df = load_annual_indicator_data(symbol, start_year)
    statement_df = build_statement_wide(
        load_annual_statement_data(symbol, start_year)
    )

    if indicator_df.empty and statement_df.empty:
        return pd.DataFrame()

    if indicator_df.empty:
        result = statement_df.copy()
        result["symbol"] = symbol
        result["name"] = None
        result["fiscal_year"] = pd.to_datetime(result["report_date"]).dt.year
        result["roe"] = None
        result["net_profit"] = result["statement_net_profit"]
        result["gross_margin"] = result["calculated_gross_margin"]
        result["debt_ratio"] = None
    else:
        result = indicator_df.merge(statement_df, on="report_date", how="left")
        result["net_profit"] = result["statement_net_profit"].combine_first(
            result["net_profit"]
        )
        result["gross_margin"] = result["gross_margin"].combine_first(
            result["calculated_gross_margin"]
        )

    result = result[
        [
            "symbol",
            "name",
            "fiscal_year",
            "report_date",
            "roe",
            "net_profit",
            "gross_margin",
            "debt_ratio",
        ]
    ].sort_values("fiscal_year")

    return result.reset_index(drop=True)


def format_snapshot(df):
    """格式化终端输出。"""

    if df.empty:
        return df

    display_df = df.copy()
    display_df = display_df.rename(
        columns={
            "symbol": "股票代码",
            "name": "股票名称",
            "fiscal_year": "年份",
            "report_date": "报告期",
            "roe": "ROE(%)",
            "net_profit": "净利润(亿元)",
            "gross_margin": "毛利率(%)",
            "debt_ratio": "资产负债率(%)",
        }
    )
    display_df["净利润(亿元)"] = display_df["净利润(亿元)"] / 100000000

    for column in ("ROE(%)", "净利润(亿元)", "毛利率(%)", "资产负债率(%)"):
        display_df[column] = pd.to_numeric(
            display_df[column],
            errors="coerce",
        ).round(2)

    return display_df


def print_snapshot(symbol=DEFAULT_SYMBOL, years=DEFAULT_YEARS, output=None):
    """打印单只股票近 N 年核心财务指标。"""

    df = load_stock_financial_snapshot(symbol=symbol, years=years)
    symbol = normalize_symbol(symbol)

    print("\n")
    print("=" * 88)
    print(f"{symbol} 近 {years} 年年报核心财务指标")
    print("指标：ROE、净利润、毛利率、资产负债率")
    print("=" * 88)

    if df.empty:
        print("没有查询到数据。请先运行 python -m data_fetch.update_financial_data")
        return df

    display_df = format_snapshot(df)
    print(display_df.to_string(index=False))

    if output is not None:
        display_df.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"\n结果已保存到: {output}")

    return df


def _first_item(group, item_names):
    """按候选科目名取第一个非空数值。"""

    for item_name in item_names:
        values = group.loc[group["item_name"] == item_name, "item_value"].dropna()

        if not values.empty:
            return values.iloc[0]

    return None


def parse_args():
    parser = argparse.ArgumentParser(description="输出单只股票近 N 年核心财务指标")
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SYMBOL,
        help="股票代码，默认 sh600519；也可输入 600519",
    )
    parser.add_argument(
        "--years",
        type=int,
        default=DEFAULT_YEARS,
        help="查看近几年年报，默认 10",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="可选：把结果保存为 CSV",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    print_snapshot(
        symbol=args.symbol,
        years=args.years,
        output=args.output,
    )
