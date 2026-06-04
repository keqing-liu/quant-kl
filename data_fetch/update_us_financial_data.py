"""美国上市公司 SEC companyfacts 财务下载占位脚本。

当前项目策略是：美国股票和 ETF 只下载行情，不下载公司财务数据。
原因是 ADR / foreign issuer 的 20-F、IFRS、非 USD 口径和美国本土 10-K/10-Q
US-GAAP 口径差异较大，混在同一套财务下载范围里容易产生空数据或不可比数据。

运行方式：

    python -m data_fetch.update_us_financial_data

当前会初始化数据库后直接退出，不访问 SEC，也不处理 WATCHLIST["US_STOCK"]。

历史说明：如果未来重新启用 SEC companyfacts，可在这个文件中恢复下载逻辑。

"""

import argparse
import json
import time
from datetime import date
from urllib.request import Request, urlopen

import pandas as pd

from config.watchlist import WATCHLIST
from data_fetch.fetch_us_market import build_us_symbol, normalize_us_ticker
from database.db_utils import get_connection, initialize_database, log_data_update


SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_USER_AGENT = "quant-kl personal research contact@example.com"
DEFAULT_START_YEAR = 2015
DEFAULT_SLEEP_SECONDS = 1
US_FINANCIAL_DOWNLOAD_ENABLED = False


SEC_TAGS = {
    "Revenues": "income_statement",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "income_statement",
    "SalesRevenueNet": "income_statement",
    "NetIncomeLoss": "income_statement",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": "income_statement",
    "IncomeTaxExpenseBenefit": "income_statement",
    "OperatingIncomeLoss": "income_statement",
    "InterestExpenseNonOperating": "income_statement",
    "InterestExpense": "income_statement",
    "NetCashProvidedByUsedInOperatingActivities": "cash_flow_statement",
    "PaymentsToAcquirePropertyPlantAndEquipment": "cash_flow_statement",
    "DepreciationDepletionAndAmortization": "cash_flow_statement",
    "DepreciationAndAmortization": "cash_flow_statement",
    "Assets": "balance_sheet",
    "Liabilities": "balance_sheet",
    "StockholdersEquity": "balance_sheet",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "balance_sheet",
    "CashAndCashEquivalentsAtCarryingValue": "balance_sheet",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": "balance_sheet",
    "ShortTermBorrowings": "balance_sheet",
    "LongTermDebtCurrent": "balance_sheet",
    "LongTermDebtNoncurrent": "balance_sheet",
    "LongTermDebtAndFinanceLeaseObligationsCurrent": "balance_sheet",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent": "balance_sheet",
    "OperatingLeaseLiabilityCurrent": "balance_sheet",
    "OperatingLeaseLiabilityNoncurrent": "balance_sheet",
    "CommonStocksIncludingAdditionalPaidInCapital": "balance_sheet",
    "CommonStockSharesOutstanding": "balance_sheet",
    "EntityCommonStockSharesOutstanding": "balance_sheet",
    "AccountsReceivableNetCurrent": "balance_sheet",
    "InventoryNet": "balance_sheet",
    "AccountsPayableCurrent": "balance_sheet",
    "AssetsCurrent": "balance_sheet",
    "LiabilitiesCurrent": "balance_sheet",
    "Goodwill": "balance_sheet",
}


def fetch_json(url):
    """请求 SEC JSON API。"""

    request = Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_cik(value):
    """把 CIK 整理成 SEC companyfacts 需要的 10 位字符串。"""

    return str(value).strip().zfill(10)


def download_sec_company_map():
    """下载 SEC ticker/CIK 映射表。"""

    payload = fetch_json(SEC_TICKER_URL)
    fields = payload.get("fields", [])
    records = []

    for item in payload.get("data", []):
        row = dict(zip(fields, item))
        ticker = normalize_us_ticker(row.get("ticker"))
        records.append(
            {
                "symbol": build_us_symbol(ticker),
                "ticker": ticker,
                "cik": normalize_cik(row.get("cik")),
                "name": row.get("name"),
                "exchange": row.get("exchange"),
                "is_active": 1,
                "data_source": "sec_company_tickers_exchange",
                "note": None,
            }
        )

    return records


def save_us_company_map(records):
    """写入 us_company_map。"""

    if not records:
        return 0

    conn = get_connection()

    try:
        sql = """
        INSERT INTO us_company_map (
            symbol,
            ticker,
            cik,
            name,
            exchange,
            is_active,
            data_source,
            note
        )
        VALUES (
            :symbol,
            :ticker,
            :cik,
            :name,
            :exchange,
            :is_active,
            :data_source,
            :note
        )
        ON CONFLICT(symbol)
        DO UPDATE SET
            ticker = excluded.ticker,
            cik = excluded.cik,
            name = excluded.name,
            exchange = excluded.exchange,
            is_active = excluded.is_active,
            data_source = excluded.data_source,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """
        cursor = conn.cursor()
        cursor.executemany(sql, records)
        rows_saved = cursor.rowcount
        conn.commit()

        return rows_saved

    finally:
        conn.close()


def get_company_record(ticker):
    """从 us_company_map 读取单只股票映射。"""

    symbol = build_us_symbol(ticker)
    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT symbol, ticker, cik, name, exchange
            FROM us_company_map
            WHERE symbol = ?
            """,
            (symbol,),
        )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "symbol": row[0],
            "ticker": row[1],
            "cik": row[2],
            "name": row[3],
            "exchange": row[4],
        }

    finally:
        conn.close()


def download_companyfacts(cik):
    """下载单家公司 SEC companyfacts。"""

    return fetch_json(SEC_COMPANYFACTS_URL.format(cik=normalize_cik(cik)))


def standardize_companyfacts(payload, symbol, start_year=None):
    """把 SEC companyfacts 转成 financial_statement_items 窄表。"""

    records = []
    facts = payload.get("facts", {}).get("us-gaap", {})

    for tag, statement_type in SEC_TAGS.items():
        tag_payload = facts.get(tag)

        if not tag_payload:
            continue

        for unit, values in tag_payload.get("units", {}).items():
            if unit not in ("USD", "shares"):
                continue

            for value in values:
                form = value.get("form")

                if form not in ("10-K", "10-Q"):
                    continue

                report_date = value.get("end")
                filed_date = value.get("filed")

                if not report_date:
                    continue

                fiscal_year = int(report_date[:4])

                if start_year is not None and fiscal_year < int(start_year):
                    continue

                item_value = value.get("val")

                if item_value is None:
                    continue

                records.append(
                    {
                        "symbol": symbol,
                        "report_date": report_date,
                        "announce_date": filed_date,
                        "statement_type": statement_type,
                        "item_name": tag,
                        "item_value": item_value,
                        "currency": unit,
                        "report_type": form,
                        "is_audited": "yes" if form == "10-K" else "no",
                        "data_source": "sec_companyfacts",
                    }
                )

    if not records:
        return pd.DataFrame(columns=STATEMENT_COLUMNS)

    df = pd.DataFrame(records)
    df = df.sort_values(
        ["symbol", "report_date", "statement_type", "item_name", "announce_date"]
    )
    df = df.drop_duplicates(
        subset=["symbol", "report_date", "statement_type", "item_name"],
        keep="last",
    )

    return df[STATEMENT_COLUMNS]


STATEMENT_COLUMNS = [
    "symbol",
    "report_date",
    "announce_date",
    "statement_type",
    "item_name",
    "item_value",
    "currency",
    "report_type",
    "is_audited",
    "data_source",
]


def save_statement_items(df):
    """写入 financial_statement_items。"""

    if df is None or df.empty:
        return 0

    df = df[STATEMENT_COLUMNS].copy()
    df = df.astype(object).where(df.notna(), None)
    conn = get_connection()

    try:
        sql = """
        INSERT INTO financial_statement_items (
            symbol,
            report_date,
            announce_date,
            statement_type,
            item_name,
            item_value,
            currency,
            report_type,
            is_audited,
            data_source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, report_date, statement_type, item_name)
        DO UPDATE SET
            announce_date = excluded.announce_date,
            item_value = excluded.item_value,
            currency = excluded.currency,
            report_type = excluded.report_type,
            is_audited = excluded.is_audited,
            data_source = excluded.data_source,
            updated_at = CURRENT_TIMESTAMP
        """
        cursor = conn.cursor()
        cursor.executemany(sql, list(df.itertuples(index=False, name=None)))
        rows_saved = cursor.rowcount
        conn.commit()

        return rows_saved

    finally:
        conn.close()


def update_companyfacts_for_ticker(ticker, start_year=None):
    """更新单只美国股票 SEC 财务数据。"""

    ticker = normalize_us_ticker(ticker)
    symbol = build_us_symbol(ticker)
    rows_downloaded = 0
    rows_saved = 0
    start_date = None
    end_date = None

    try:
        record = get_company_record(ticker)

        if record is None:
            raise ValueError(f"找不到 {ticker} 的 SEC CIK 映射，请先同步 us_company_map")

        payload = download_companyfacts(record["cik"])
        df = standardize_companyfacts(payload, symbol=symbol, start_year=start_year)

        if df.empty:
            log_data_update(
                symbol=symbol,
                asset_type="US_STOCK_FINANCIAL",
                rows_downloaded=0,
                rows_inserted=0,
                status="empty",
                message="SEC companyfacts 返回空数据",
                data_source="sec_companyfacts",
            )
            print(f"{symbol} SEC companyfacts 返回空数据")
            return "empty"

        rows_downloaded = len(df)
        start_date = df["report_date"].min()
        end_date = df["report_date"].max()
        rows_saved = save_statement_items(df)
        log_data_update(
            symbol=symbol,
            asset_type="US_STOCK_FINANCIAL",
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="success",
            message="SEC companyfacts 更新成功",
            data_source="sec_companyfacts",
        )
        print(f"{symbol} SEC 财务更新完成：下载 {rows_downloaded} 行，写入/更新 {rows_saved} 行")

        return "success"

    except Exception as e:
        log_data_update(
            symbol=symbol,
            asset_type="US_STOCK_FINANCIAL",
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="failed",
            message=str(e),
            data_source="sec_companyfacts",
        )
        print(f"{symbol} SEC 财务更新失败: {e}")
        return "failed"


def load_watchlist_us_stocks():
    """读取 watchlist 中的美国股票，不包括 ETF。

    当前美国股票只用于行情下载，因此财务下载默认不使用这个列表。
    """

    return WATCHLIST.get("US_STOCK", [])


def update_us_financial_data(tickers=None, start_year=None, sleep_seconds=DEFAULT_SLEEP_SECONDS):
    """批量更新美国股票 SEC 财务数据。

    当前项目关闭美国公司财务下载；美股和 ETF 只保留行情数据。
    """

    initialize_database()

    requested_tickers = list(tickers or [])

    if not US_FINANCIAL_DOWNLOAD_ENABLED:
        print("美国股票财务下载已关闭：US_STOCK/US_ETF 当前只用于行情下载。")
        if requested_tickers:
            print(f"已忽略手动传入的 ticker: {', '.join(requested_tickers)}")
        print("未访问 SEC companyfacts，未写入 financial_statement_items。")
        return "disabled"

    if start_year is None:
        start_year = DEFAULT_START_YEAR

    map_records = download_sec_company_map()
    rows_saved = save_us_company_map(map_records)
    print(f"SEC ticker/CIK 映射更新完成：{rows_saved} 行")

    if tickers is None:
        tickers = load_watchlist_us_stocks()

    tickers = list(tickers)

    for index, ticker in enumerate(tickers, start=1):
        print(f"[{index}/{len(tickers)}] 开始更新 {ticker}")
        update_companyfacts_for_ticker(ticker, start_year=start_year)

        if index < len(tickers):
            time.sleep(sleep_seconds)


def parse_args():
    parser = argparse.ArgumentParser(description="美国股票财务下载占位脚本；当前已关闭")
    parser.add_argument(
        "--ticker",
        action="append",
        help="当前会被忽略；美国股票只下载行情，不下载财务数据",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="当前会被忽略；保留给未来重新启用 SEC 财务下载时使用",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="每只股票之间等待多少秒；默认 1 秒",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    update_us_financial_data(
        tickers=args.ticker,
        start_year=args.start_year,
        sleep_seconds=args.sleep,
    )
