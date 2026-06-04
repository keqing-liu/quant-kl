"""计算巴菲特式基本面衍生指标并写入 SQLite。

运行方式：

    python3 -m analysis.calculate_buffett_metrics

只计算单只股票：

    python3 -m analysis.calculate_buffett_metrics --symbol sh600519 --annual-only
"""

import argparse
from datetime import date

import pandas as pd

from database.db_utils import get_connection, initialize_database


BUFFETT_COLUMNS = [
    "symbol",
    "report_date",
    "announce_date",
    "fiscal_year",
    "fiscal_period",
    "revenue",
    "net_profit",
    "operating_cash_flow",
    "capital_expenditure",
    "depreciation_amortization",
    "free_cash_flow",
    "free_cash_flow_margin",
    "market_cap",
    "free_cash_flow_yield",
    "cfo_to_net_profit",
    "cfo_to_revenue",
    "capex_to_cfo",
    "capex_to_depreciation",
    "owner_earnings_approx",
    "nopat",
    "invested_capital",
    "roic",
    "net_debt",
    "net_debt_ratio",
    "interest_coverage",
    "goodwill_to_equity",
    "receivable_to_revenue",
    "inventory_to_revenue",
    "working_capital",
    "working_capital_change",
    "data_source",
]


PROFIT_ITEMS = {
    "revenue": ["营业总收入", "营业收入"],
    "net_profit": ["归属于母公司所有者的净利润", "净利润"],
    "total_profit": ["利润总额"],
    "income_tax": ["所得税费用"],
    "operating_profit": ["营业利润"],
    "interest_expense": ["利息费用", "利息支出"],
}

CASHFLOW_ITEMS = {
    "operating_cash_flow": ["经营活动产生的现金流量净额"],
    "capital_expenditure": [
        "购建固定资产、无形资产和其他长期资产所支付的现金",
    ],
    "depreciation_amortization": [
        "固定资产折旧、油气资产折耗、生产性生物资产折旧",
        "无形资产摊销",
        "长期待摊费用摊销",
    ],
}

BALANCE_ITEMS = {
    "cash": ["货币资金"],
    "short_borrowing": ["短期借款"],
    "noncurrent_liab_due_one_year": ["一年内到期的非流动负债"],
    "long_borrowing": ["长期借款"],
    "bond_payable": ["应付债券"],
    "lease_liability": ["租赁负债"],
    "total_assets": ["资产总计"],
    "total_liabilities": ["负债合计"],
    "total_equity": [
        "所有者权益(或股东权益)合计",
        "归属于母公司股东权益合计",
    ],
    "share_capital": ["实收资本(或股本)"],
    "accounts_receivable": ["应收账款", "应收票据及应收账款"],
    "inventory": ["存货"],
    "accounts_payable": ["应付账款", "应付票据及应付账款"],
    "current_assets": ["流动资产合计"],
    "current_liabilities": ["流动负债合计"],
    "goodwill": ["商誉"],
}


US_PROFIT_ITEMS = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "net_profit": ["NetIncomeLoss"],
    "total_profit": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "operating_profit": ["OperatingIncomeLoss", "NetIncomeLoss"],
    "interest_expense": ["InterestExpenseNonOperating", "InterestExpense"],
}

US_CASHFLOW_ITEMS = {
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
    ],
}

US_BALANCE_ITEMS = {
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_borrowing": ["ShortTermBorrowings"],
    "noncurrent_liab_due_one_year": [
        "LongTermDebtCurrent",
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
    ],
    "long_borrowing": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    ],
    "bond_payable": [],
    "lease_liability": [
        "OperatingLeaseLiabilityCurrent",
        "OperatingLeaseLiabilityNoncurrent",
    ],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "total_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "share_capital": [
        "EntityCommonStockSharesOutstanding",
        "CommonStockSharesOutstanding",
    ],
    "accounts_receivable": ["AccountsReceivableNetCurrent"],
    "inventory": ["InventoryNet"],
    "accounts_payable": ["AccountsPayableCurrent"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "goodwill": ["Goodwill"],
}


def load_statement_items(symbols=None, start_year=None, annual_only=False):
    """读取三大报表窄表数据。"""

    conn = get_connection()

    try:
        sql = """
        SELECT
            symbol,
            report_date,
            announce_date,
            statement_type,
            item_name,
            item_value
        FROM financial_statement_items
        WHERE 1 = 1
        """
        params = []

        if symbols:
            placeholders = ", ".join(["?"] * len(symbols))
            sql += f" AND symbol IN ({placeholders})"
            params.extend(symbols)

        if start_year is not None:
            sql += " AND CAST(substr(report_date, 1, 4) AS INTEGER) >= ?"
            params.append(int(start_year))

        if annual_only:
            sql += """
            AND (
                substr(report_date, 6, 5) = '12-31'
                OR report_type = '10-K'
            )
            """

        sql += " ORDER BY symbol, report_date"

        return pd.read_sql(sql, conn, params=params)

    finally:
        conn.close()


def load_financial_indicators(symbols=None, start_year=None, annual_only=False):
    """读取已经直接下载的新浪财务指标，用于补充比率字段。"""

    conn = get_connection()

    try:
        sql = """
        SELECT
            symbol,
            report_date,
            interest_coverage
        FROM financial_indicators
        WHERE 1 = 1
        """
        params = []

        if symbols:
            placeholders = ", ".join(["?"] * len(symbols))
            sql += f" AND symbol IN ({placeholders})"
            params.extend(symbols)

        if start_year is not None:
            sql += " AND fiscal_year >= ?"
            params.append(int(start_year))

        if annual_only:
            sql += " AND fiscal_period = 'Q4'"

        return pd.read_sql(sql, conn, params=params)

    finally:
        conn.close()


def load_price_data(symbols):
    """读取已有日线行情，用于在报告期层面估算市值。"""

    if not symbols:
        return pd.DataFrame(columns=["symbol", "date", "close"])

    conn = get_connection()

    try:
        placeholders = ", ".join(["?"] * len(symbols))
        sql = f"""
        SELECT symbol, date, close
        FROM price_data
        WHERE symbol IN ({placeholders})
          AND close IS NOT NULL
        ORDER BY symbol, date
        """

        return pd.read_sql(sql, conn, params=list(symbols))

    finally:
        conn.close()


def calculate_buffett_metrics(symbols=None, start_year=None, annual_only=False):
    """计算巴菲特式衍生指标。"""

    statement_df = load_statement_items(
        symbols=symbols,
        start_year=start_year,
        annual_only=annual_only,
    )

    if statement_df.empty:
        return pd.DataFrame(columns=BUFFETT_COLUMNS)

    base_df = build_report_base(statement_df)
    indicator_df = load_financial_indicators(
        symbols=symbols,
        start_year=start_year,
        annual_only=annual_only,
    )

    if not indicator_df.empty:
        base_df = base_df.merge(
            indicator_df,
            on=["symbol", "report_date"],
            how="left",
        )
    else:
        base_df["interest_coverage"] = None

    price_df = load_price_data(base_df["symbol"].drop_duplicates().tolist())
    base_df = attach_market_cap(base_df, price_df)
    result = compute_metrics(base_df)

    return result[BUFFETT_COLUMNS]


def build_report_base(statement_df):
    """把三大报表 item 窄表整理成每个报告期一行。"""

    rows = []

    for (symbol, report_date), group in statement_df.groupby(["symbol", "report_date"]):
        row = {
            "symbol": symbol,
            "report_date": report_date,
            "announce_date": _last_non_null(group["announce_date"]),
        }
        row["fiscal_year"] = int(report_date[:4])
        row["fiscal_period"] = f"Q{pd.Timestamp(report_date).quarter}"

        if _is_us_report_group(group):
            profit_group = group[group["statement_type"] == "income_statement"]
            cashflow_group = group[group["statement_type"] == "cash_flow_statement"]
            balance_group = group[group["statement_type"] == "balance_sheet"]
            profit_items = US_PROFIT_ITEMS
            cashflow_items = US_CASHFLOW_ITEMS
            balance_items = US_BALANCE_ITEMS
        else:
            profit_group = group[group["statement_type"] == "利润表"]
            cashflow_group = group[group["statement_type"] == "现金流量表"]
            balance_group = group[group["statement_type"] == "资产负债表"]
            profit_items = PROFIT_ITEMS
            cashflow_items = CASHFLOW_ITEMS
            balance_items = BALANCE_ITEMS

        for output_column, item_names in profit_items.items():
            row[output_column] = _first_item_value(profit_group, item_names)

        for output_column, item_names in cashflow_items.items():
            if output_column == "depreciation_amortization":
                row[output_column] = _sum_item_values(cashflow_group, item_names)
            elif output_column == "lease_liability":
                row[output_column] = _sum_item_values(cashflow_group, item_names)
            else:
                row[output_column] = _first_item_value(cashflow_group, item_names)

        for output_column, item_names in balance_items.items():
            if output_column in ("lease_liability",):
                row[output_column] = _sum_item_values(balance_group, item_names)
            else:
                row[output_column] = _first_item_value(balance_group, item_names)

        rows.append(row)

    result = pd.DataFrame(rows)

    return result.sort_values(["symbol", "report_date"]).reset_index(drop=True)


def attach_market_cap(report_df, price_df):
    """用公告日后最近收盘价和股本估算报告期市值。"""

    report_df = report_df.copy()
    report_df["market_cap"] = None

    if price_df.empty:
        return report_df

    price_df = price_df.copy()
    price_df["date"] = pd.to_datetime(price_df["date"], errors="coerce")

    price_map = {
        symbol: group.dropna(subset=["date"]).sort_values("date")
        for symbol, group in price_df.groupby("symbol")
    }

    for index, row in report_df.iterrows():
        share_capital = row.get("share_capital")

        if pd.isna(share_capital):
            continue

        anchor_date = row.get("announce_date") or row.get("report_date")
        anchor_date = pd.to_datetime(anchor_date, errors="coerce")

        if pd.isna(anchor_date):
            continue

        symbol_prices = price_map.get(row["symbol"])

        if symbol_prices is None or symbol_prices.empty:
            continue

        matched = symbol_prices[symbol_prices["date"] >= anchor_date]

        if matched.empty:
            continue

        close = matched.iloc[0]["close"]

        if pd.isna(close):
            continue

        report_df.at[index, "market_cap"] = float(close) * float(share_capital)

    return report_df


def compute_metrics(df):
    """按报告期计算衍生指标。"""

    result = df.copy()
    numeric_columns = [
        "revenue",
        "net_profit",
        "total_profit",
        "income_tax",
        "operating_profit",
        "interest_expense",
        "operating_cash_flow",
        "capital_expenditure",
        "depreciation_amortization",
        "cash",
        "short_borrowing",
        "noncurrent_liab_due_one_year",
        "long_borrowing",
        "bond_payable",
        "lease_liability",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "share_capital",
        "accounts_receivable",
        "inventory",
        "accounts_payable",
        "current_assets",
        "current_liabilities",
        "goodwill",
        "market_cap",
        "interest_coverage",
    ]

    for column in numeric_columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")

    result["capital_expenditure"] = result["capital_expenditure"].abs()
    result["free_cash_flow"] = (
        result["operating_cash_flow"] - result["capital_expenditure"]
    )
    result["free_cash_flow_margin"] = _safe_div(
        result["free_cash_flow"],
        result["revenue"],
    )
    result["free_cash_flow_yield"] = _safe_div(
        result["free_cash_flow"],
        result["market_cap"],
    )
    result["cfo_to_net_profit"] = _safe_div(
        result["operating_cash_flow"],
        result["net_profit"],
    )
    result["cfo_to_revenue"] = _safe_div(
        result["operating_cash_flow"],
        result["revenue"],
    )
    result["capex_to_cfo"] = _safe_div(
        result["capital_expenditure"],
        result["operating_cash_flow"],
    )
    result["capex_to_depreciation"] = _safe_div(
        result["capital_expenditure"],
        result["depreciation_amortization"],
    )
    result["owner_earnings_approx"] = result.apply(_owner_earnings, axis=1)
    result["nopat"] = result.apply(_nopat, axis=1)
    result["invested_capital"] = result.apply(_invested_capital, axis=1)
    result["roic"] = _safe_div(result["nopat"], result["invested_capital"])
    result["net_debt"] = result.apply(_net_debt, axis=1)
    result["net_debt_ratio"] = _safe_div(result["net_debt"], result["total_equity"])
    result["goodwill_to_equity"] = _safe_div(result["goodwill"], result["total_equity"])
    result["receivable_to_revenue"] = _safe_div(
        result["accounts_receivable"],
        result["revenue"],
    )
    result["inventory_to_revenue"] = _safe_div(result["inventory"], result["revenue"])
    result["working_capital"] = result.apply(_working_capital, axis=1)
    result["working_capital_change"] = (
        result.groupby("symbol")["working_capital"].diff()
    )
    result["data_source"] = result["symbol"].apply(_metric_data_source)

    return result


def save_buffett_metrics(df):
    """把衍生指标写入 buffett_metrics 表。"""

    if df is None or df.empty:
        return 0

    df = df[BUFFETT_COLUMNS].copy()
    df = df.astype(object).where(df.notna(), None)
    conn = get_connection()

    try:
        columns = BUFFETT_COLUMNS
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        update_columns = [
            column for column in columns if column not in ("symbol", "report_date")
        ]
        update_sql = ",\n            ".join(
            [f"{column} = excluded.{column}" for column in update_columns]
            + ["updated_at = CURRENT_TIMESTAMP"]
        )
        sql = f"""
        INSERT INTO buffett_metrics (
            {column_sql}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT(symbol, report_date)
        DO UPDATE SET
            {update_sql}
        """
        cursor = conn.cursor()
        cursor.executemany(sql, list(df.itertuples(index=False, name=None)))
        rows_saved = cursor.rowcount
        conn.commit()

        return rows_saved

    finally:
        conn.close()


def _first_item_value(group, item_names):
    """按候选 item_name 取第一个非空值。"""

    for item_name in item_names:
        values = group.loc[group["item_name"] == item_name, "item_value"].dropna()

        if not values.empty:
            return values.iloc[0]

    return None


def _is_us_report_group(group):
    """判断当前报告期是否来自 SEC companyfacts。"""

    return group["statement_type"].isin(
        ["income_statement", "balance_sheet", "cash_flow_statement"]
    ).any()


def _metric_data_source(symbol):
    """标记衍生指标来自 A 股新浪财报还是美国 SEC facts。"""

    if str(symbol).startswith("us_"):
        return "calculated_from_sec_companyfacts"

    return "calculated_from_sina_financial_report"


def _sum_item_values(group, item_names):
    """对多个可选 item_name 求和；全部缺失时返回 None。"""

    values = []

    for item_name in item_names:
        matches = group.loc[group["item_name"] == item_name, "item_value"].dropna()

        if not matches.empty:
            values.append(matches.iloc[0])

    if not values:
        return None

    return sum(values)


def _last_non_null(series):
    values = series.dropna()

    if values.empty:
        return None

    return values.iloc[-1]


def _safe_div(numerator, denominator):
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")

    return numerator.where(denominator != 0) / denominator.where(denominator != 0)


def _owner_earnings(row):
    cfo = row.get("operating_cash_flow")
    capex = row.get("capital_expenditure")
    depreciation = row.get("depreciation_amortization")

    if pd.isna(cfo):
        return None

    if pd.isna(capex):
        return cfo

    if pd.isna(depreciation):
        return cfo - capex

    return cfo - min(capex, depreciation)


def _nopat(row):
    operating_profit = row.get("operating_profit")
    total_profit = row.get("total_profit")
    income_tax = row.get("income_tax")

    if pd.isna(operating_profit):
        return None

    tax_rate = 0.25

    if not pd.isna(total_profit) and total_profit != 0 and not pd.isna(income_tax):
        tax_rate = max(0, min(1, income_tax / total_profit))

    return operating_profit * (1 - tax_rate)


def _invested_capital(row):
    total_equity = row.get("total_equity")
    interest_bearing_debt = _interest_bearing_debt(row)

    if pd.isna(total_equity) and pd.isna(interest_bearing_debt):
        return None

    return (0 if pd.isna(total_equity) else total_equity) + (
        0 if pd.isna(interest_bearing_debt) else interest_bearing_debt
    )


def _net_debt(row):
    interest_bearing_debt = _interest_bearing_debt(row)
    cash = row.get("cash")

    if pd.isna(interest_bearing_debt) and pd.isna(cash):
        return None

    return (0 if pd.isna(interest_bearing_debt) else interest_bearing_debt) - (
        0 if pd.isna(cash) else cash
    )


def _interest_bearing_debt(row):
    debt_columns = [
        "short_borrowing",
        "noncurrent_liab_due_one_year",
        "long_borrowing",
        "bond_payable",
        "lease_liability",
    ]
    values = [row.get(column) for column in debt_columns]

    if all(pd.isna(value) for value in values):
        return None

    return sum(0 if pd.isna(value) else value for value in values)


def _working_capital(row):
    current_assets = row.get("current_assets")
    current_liabilities = row.get("current_liabilities")

    if pd.isna(current_assets) or pd.isna(current_liabilities):
        return None

    return current_assets - current_liabilities


def parse_args():
    parser = argparse.ArgumentParser(description="计算巴菲特式基本面衍生指标")
    parser.add_argument(
        "--symbol",
        action="append",
        help="只计算指定股票，可重复传入，例如 --symbol sh600519 --symbol sz000001",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="只计算该年份之后的报告期；默认近 10 年",
    )
    parser.add_argument(
        "--annual-only",
        action="store_true",
        help="只计算年报 Q4 / 12-31 报告期",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    initialize_database()
    start_year = args.start_year

    if start_year is None:
        start_year = date.today().year - 10

    df = calculate_buffett_metrics(
        symbols=args.symbol,
        start_year=start_year,
        annual_only=args.annual_only,
    )

    rows_saved = save_buffett_metrics(df)
    print(f"巴菲特衍生指标计算完成：生成 {len(df)} 行，写入/更新 {rows_saved} 行")


if __name__ == "__main__":
    main()
