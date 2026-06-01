"""批量更新股票财务指标到 SQLite。

运行方式：

    python3 -m data_fetch.update_financial_data

也可以只更新单只股票，便于调试：

    python3 -m data_fetch.update_financial_data --symbol sh600519
"""

import argparse
import time

from database.db_utils import (
    get_connection,
    initialize_database,
    log_data_update,
)
from data_fetch.fetch_financial import (
    FINANCIAL_COLUMNS,
    download_financial_indicators,
)


DEFAULT_START_YEAR = 2015
DEFAULT_SLEEP_SECONDS = 8
DEFAULT_RETRIES = 2
DATA_SOURCE = "akshare_sina_financial_indicator"


def load_stock_universe_symbols():
    """从 stock_universe 读取可用于财报筛选的股票列表。"""

    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT symbol
            FROM stock_universe
            WHERE is_active = 1
              AND is_st = 0
              AND is_delisting_risk = 0
            ORDER BY symbol
            """
        )

        return [row[0] for row in cursor.fetchall()]

    finally:
        conn.close()


def get_latest_financial_report_date(symbol):
    """查询某只股票已保存的最新财报报告期。"""

    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT MAX(report_date)
            FROM financial_indicators
            WHERE symbol = ?
            """,
            (symbol,),
        )

        result = cursor.fetchone()

        if result is None:
            return None

        return result[0]

    finally:
        conn.close()


def save_financial_indicators(df):
    """把整理后的财务指标写入 financial_indicators 表。"""

    if df is None or df.empty:
        return 0

    # FINANCIAL_COLUMNS 规定了 DataFrame 列顺序，也要和下面 INSERT 的字段顺序一致。
    # 这一步可以防止 AkShare 原始字段混入数据库写入逻辑。
    df = df[FINANCIAL_COLUMNS].copy()

    # pandas 的 NaN 不能直接作为 SQLite NULL 使用。
    # 统一把缺失值转成 None，写入后就是数据库里的 NULL。
    df = df.astype(object).where(df.notna(), None)

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # 用 UPSERT 保证同一 symbol + report_date 可以重复刷新。
        # 这样既支持增量更新，也支持 --force-refresh 重新写入已有报告期。
        sql = """
        INSERT INTO financial_indicators (
            symbol,
            report_date,
            announce_date,
            period_type,
            fiscal_year,
            fiscal_period,
            roe,
            revenue,
            revenue_yoy,
            net_profit,
            net_profit_yoy,
            gross_margin,
            debt_ratio,
            operating_cash_flow,
            eps,
            data_source
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(symbol, report_date)
        DO UPDATE SET
            announce_date = excluded.announce_date,
            period_type = excluded.period_type,
            fiscal_year = excluded.fiscal_year,
            fiscal_period = excluded.fiscal_period,
            roe = excluded.roe,
            revenue = excluded.revenue,
            revenue_yoy = excluded.revenue_yoy,
            net_profit = excluded.net_profit,
            net_profit_yoy = excluded.net_profit_yoy,
            gross_margin = excluded.gross_margin,
            debt_ratio = excluded.debt_ratio,
            operating_cash_flow = excluded.operating_cash_flow,
            eps = excluded.eps,
            data_source = excluded.data_source,
            updated_at = CURRENT_TIMESTAMP
        """

        data = list(df.itertuples(index=False, name=None))
        cursor.executemany(sql, data)
        # executemany + ON CONFLICT 下，rowcount 表示本次影响的行数。
        # 这里命名为 rows_saved，比 rows_inserted 更贴近 upsert 语义。
        rows_saved = cursor.rowcount

        conn.commit()

        return rows_saved

    finally:
        conn.close()


def update_financial_indicators_for_symbol(
    symbol,
    start_year,
    force_refresh=False,
):
    """更新单只股票的财务指标，并写入更新日志。"""

    # 用本地已保存的最大 report_date 做增量边界。
    # 注意：这不是公告日边界；未来做严格历史回测时，需要补 announce_date。
    latest_date_before = get_latest_financial_report_date(symbol)
    rows_downloaded = 0
    rows_saved = 0
    start_date = None
    end_date = None

    try:
        df = download_financial_indicators(
            symbol=symbol,
            start_year=start_year,
        )

        if df is None or df.empty:
            log_data_update(
                symbol=symbol,
                asset_type="STOCK_FINANCIAL",
                latest_date_before=latest_date_before,
                start_date=None,
                end_date=None,
                rows_downloaded=0,
                rows_inserted=0,
                status="empty",
                message="财务指标接口返回空数据",
                data_source=DATA_SOURCE,
            )

            print(f"{symbol} 财务指标接口返回空数据")
            return "empty"

        rows_downloaded = len(df)
        downloaded_start_date = df["report_date"].min()
        downloaded_end_date = df["report_date"].max()

        # original_df 保留接口返回的完整结果。
        # 当 --force-refresh 打开时，即使没有新增报告期，也可以刷新已有字段口径。
        original_df = df

        if latest_date_before is not None:
            # report_date 使用 YYYY-MM-DD 字符串格式，按字典序比较等价于日期比较。
            df = df[df["report_date"] > latest_date_before]

        if df.empty:
            if force_refresh:
                rows_saved = save_financial_indicators(original_df)

                log_data_update(
                    symbol=symbol,
                    asset_type="STOCK_FINANCIAL",
                    latest_date_before=latest_date_before,
                    start_date=downloaded_start_date,
                    end_date=downloaded_end_date,
                    rows_downloaded=rows_downloaded,
                    rows_inserted=rows_saved,
                    status="force_refresh",
                    message="财务指标已是最新，强制刷新已有记录",
                    data_source=DATA_SOURCE,
                )

                print(
                    f"{symbol} 财务指标已是最新，"
                    f"已强制刷新 {rows_saved} 行"
                )
                return "success"

            log_data_update(
                symbol=symbol,
                asset_type="STOCK_FINANCIAL",
                latest_date_before=latest_date_before,
                start_date=downloaded_start_date,
                end_date=downloaded_end_date,
                rows_downloaded=rows_downloaded,
                rows_inserted=0,
                status="no_new_data",
                message="财务指标已经是最新，无需写入",
                data_source=DATA_SOURCE,
            )

            print(
                f"{symbol} 财务指标已是最新："
                f"数据库最新报告期 {latest_date_before}，"
                f"接口最新报告期 {downloaded_end_date}"
            )
            return "no_new_data"

        start_date = df["report_date"].min()
        end_date = df["report_date"].max()

        rows_saved = save_financial_indicators(df)

        log_data_update(
            symbol=symbol,
            asset_type="STOCK_FINANCIAL",
            latest_date_before=latest_date_before,
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="success",
            message="财务指标更新成功",
            data_source=DATA_SOURCE,
        )

        print(
            f"{symbol} 财务指标更新完成："
            f"下载 {rows_downloaded} 行，写入/更新 {rows_saved} 行"
        )

        return "success"

    except Exception as e:
        log_data_update(
            symbol=symbol,
            asset_type="STOCK_FINANCIAL",
            latest_date_before=latest_date_before,
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="failed",
            message=str(e),
            data_source=DATA_SOURCE,
        )

        print(f"{symbol} 财务指标更新失败: {e}")
        return "failed"


def update_symbol_with_retries(
    symbol,
    start_year,
    retries,
    sleep_seconds,
    force_refresh=False,
):
    """更新单只股票，失败时按次数重试。"""

    # retries 表示失败后的“额外重试次数”，所以总尝试次数是 retries + 1。
    attempts = retries + 1

    for attempt in range(1, attempts + 1):
        status = update_financial_indicators_for_symbol(
            symbol=symbol,
            start_year=start_year,
            force_refresh=force_refresh,
        )

        # empty / no_new_data 是正常结束状态，不需要重试。
        if status in ("success", "empty", "no_new_data"):
            return status

        if attempt < attempts:
            print(
                f"{symbol} 第 {attempt} 次尝试失败，"
                f"等待 {sleep_seconds} 秒后重试"
            )
            time.sleep(sleep_seconds)

    return "failed"


def update_financial_indicators(
    symbols=None,
    start_year=None,
    limit=None,
    offset=0,
    sleep_seconds=DEFAULT_SLEEP_SECONDS,
    retries=DEFAULT_RETRIES,
    force_refresh=False,
):
    """批量更新股票财务指标。"""

    initialize_database()

    if start_year is None:
        start_year = DEFAULT_START_YEAR

    if symbols is None:
        # 默认从 stock_universe 读取股票池。
        # 因此首次使用时，需要先运行 python -m data_fetch.update_stock_universe。
        symbols = load_stock_universe_symbols()

    symbols = list(symbols)

    # limit / offset 用于把全市场任务拆成小批次，降低接口限速和中断风险。
    if offset:
        symbols = symbols[offset:]

    if limit is not None:
        symbols = symbols[:limit]

    if not symbols:
        print("stock_universe 中没有可更新的股票")
        return

    print(
        f"准备更新 {len(symbols)} 只股票的财务指标，"
        f"起始年份: {start_year}，"
        f"间隔: {sleep_seconds} 秒，"
        f"失败重试: {retries} 次，"
        f"强制刷新: {force_refresh}"
    )

    for index, symbol in enumerate(symbols, start=1):
        print(f"[{index}/{len(symbols)}] 开始更新 {symbol}")

        update_symbol_with_retries(
            symbol=symbol,
            start_year=start_year,
            retries=retries,
            sleep_seconds=sleep_seconds,
            force_refresh=force_refresh,
        )

        if index < len(symbols):
            print(f"等待 {sleep_seconds} 秒后继续下一只股票")
            time.sleep(sleep_seconds)


def parse_args():
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(
        description="批量更新股票财务指标到 SQLite"
    )

    parser.add_argument(
        "--symbol",
        action="append",
        help="只更新指定股票，可重复传入，例如 --symbol sh600519 --symbol sz000001",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="只保留该年份之后的财务指标；默认从 2015 年开始",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="本次最多更新多少只股票，用于分批下载",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="从股票池第几只开始更新，用于分批下载",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="每只股票之间等待多少秒；默认 12 秒，约每分钟 5 只",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help="单只股票失败后重试次数；默认 2 次",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="即使本地已是最新，也重新写入已有报告期，用于刷新字段口径",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    update_financial_indicators(
        symbols=args.symbol,
        start_year=args.start_year,
        limit=args.limit,
        offset=args.offset,
        sleep_seconds=args.sleep,
        retries=args.retries,
        force_refresh=args.force_refresh,
    )
