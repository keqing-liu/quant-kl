"""批量更新股票基本财务数据到 SQLite。

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
    STATEMENT_COLUMNS,
    download_financial_indicators,
    download_financial_statements,
)


DEFAULT_START_YEAR = 2015
DEFAULT_SLEEP_SECONDS = 8
DEFAULT_RETRIES = 2
DEFAULT_DATASETS = ("indicators", "statements")

DATASET_CONFIG = {
    "indicators": {
        "asset_type": "STOCK_FINANCIAL_INDICATORS",
        "table": "financial_indicators",
        "columns": FINANCIAL_COLUMNS,
        "key_columns": ("symbol", "report_date"),
        "date_column": "report_date",
        "data_source": "akshare_sina_financial_indicator",
    },
    "statements": {
        "asset_type": "STOCK_FINANCIAL_STATEMENTS",
        "table": "financial_statement_items",
        "columns": STATEMENT_COLUMNS,
        "key_columns": ("symbol", "report_date", "statement_type", "item_name"),
        "date_column": "report_date",
        "data_source": "akshare_sina_financial_report",
    },
}


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


def get_latest_dataset_date(symbol, dataset):
    """查询某只股票某类财务数据已保存的最新日期。"""

    config = DATASET_CONFIG[dataset]
    conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT MAX({config['date_column']})
            FROM {config['table']}
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


def save_dataset(df, dataset):
    """把标准化后的财务数据写入对应表。"""

    if df is None or df.empty:
        return 0

    config = DATASET_CONFIG[dataset]
    columns = config["columns"]

    df = df[columns].copy()

    df = df.astype(object).where(df.notna(), None)

    conn = get_connection()

    try:
        cursor = conn.cursor()
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        update_columns = [column for column in columns if column not in config["key_columns"]]
        update_sql = ",\n            ".join(
            [f"{column} = excluded.{column}" for column in update_columns]
            + ["updated_at = CURRENT_TIMESTAMP"]
        )
        key_sql = ", ".join(config["key_columns"])

        sql = f"""
        INSERT INTO {config['table']} (
            {column_sql}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT({key_sql})
        DO UPDATE SET
            {update_sql}
        """

        data = list(df.itertuples(index=False, name=None))
        cursor.executemany(sql, data)
        rows_saved = cursor.rowcount
        conn.commit()

        return rows_saved

    finally:
        conn.close()


def download_dataset(symbol, dataset, start_year):
    """按数据集调用对应下载函数。"""

    if dataset == "indicators":
        return download_financial_indicators(symbol=symbol, start_year=start_year)

    if dataset == "statements":
        return download_financial_statements(symbol=symbol, start_year=start_year)

    raise ValueError(f"未知财务数据集: {dataset}")


def update_dataset_for_symbol(symbol, dataset, start_year, force_refresh=False):
    """更新单只股票的某类财务数据，并写入更新日志。"""

    config = DATASET_CONFIG[dataset]
    latest_date_before = get_latest_dataset_date(symbol, dataset)
    rows_downloaded = 0
    rows_saved = 0
    start_date = None
    end_date = None

    try:
        df = download_dataset(
            symbol=symbol,
            dataset=dataset,
            start_year=start_year,
        )

        if df is None or df.empty:
            log_data_update(
                symbol=symbol,
                asset_type=config["asset_type"],
                latest_date_before=latest_date_before,
                start_date=None,
                end_date=None,
                rows_downloaded=0,
                rows_inserted=0,
                status="empty",
                message=f"{dataset} 接口返回空数据",
                data_source=config["data_source"],
            )
            print(f"{symbol} {dataset} 接口返回空数据")
            return "empty"

        date_column = config["date_column"]
        rows_downloaded = len(df)
        downloaded_start_date = df[date_column].min()
        downloaded_end_date = df[date_column].max()
        original_df = df

        if latest_date_before is not None:
            df = df[df[date_column] > latest_date_before]

        if df.empty:
            if force_refresh:
                rows_saved = save_dataset(original_df, dataset)
                log_data_update(
                    symbol=symbol,
                    asset_type=config["asset_type"],
                    latest_date_before=latest_date_before,
                    start_date=downloaded_start_date,
                    end_date=downloaded_end_date,
                    rows_downloaded=rows_downloaded,
                    rows_inserted=rows_saved,
                    status="force_refresh",
                    message=f"{dataset} 已是最新，强制刷新已有记录",
                    data_source=config["data_source"],
                )
                print(f"{symbol} {dataset} 已强制刷新 {rows_saved} 行")
                return "success"

            log_data_update(
                symbol=symbol,
                asset_type=config["asset_type"],
                latest_date_before=latest_date_before,
                start_date=downloaded_start_date,
                end_date=downloaded_end_date,
                rows_downloaded=rows_downloaded,
                rows_inserted=0,
                status="no_new_data",
                message=f"{dataset} 已经是最新，无需写入",
                data_source=config["data_source"],
            )
            print(
                f"{symbol} {dataset} 已是最新："
                f"数据库最新 {latest_date_before}，接口最新 {downloaded_end_date}"
            )
            return "no_new_data"

        start_date = df[date_column].min()
        end_date = df[date_column].max()
        rows_saved = save_dataset(df, dataset)

        log_data_update(
            symbol=symbol,
            asset_type=config["asset_type"],
            latest_date_before=latest_date_before,
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="success",
            message=f"{dataset} 更新成功",
            data_source=config["data_source"],
        )
        print(
            f"{symbol} {dataset} 更新完成："
            f"下载 {rows_downloaded} 行，写入/更新 {rows_saved} 行"
        )

        return "success"

    except Exception as e:
        log_data_update(
            symbol=symbol,
            asset_type=config["asset_type"],
            latest_date_before=latest_date_before,
            start_date=start_date,
            end_date=end_date,
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="failed",
            message=str(e),
            data_source=config["data_source"],
        )
        print(f"{symbol} {dataset} 更新失败: {e}")
        return "failed"


def update_symbol_with_retries(
    symbol,
    datasets,
    start_year,
    retries,
    sleep_seconds,
    force_refresh=False,
):
    """更新单只股票，失败时按次数重试。"""

    final_statuses = []

    for dataset in datasets:
        attempts = retries + 1

        for attempt in range(1, attempts + 1):
            status = update_dataset_for_symbol(
                symbol=symbol,
                dataset=dataset,
                start_year=start_year,
                force_refresh=force_refresh,
            )

            if status in ("success", "empty", "no_new_data"):
                final_statuses.append(status)
                break

            if attempt < attempts:
                print(
                    f"{symbol} {dataset} 第 {attempt} 次尝试失败，"
                    f"等待 {sleep_seconds} 秒后重试"
                )
                time.sleep(sleep_seconds)
        else:
            final_statuses.append("failed")

    if "failed" in final_statuses:
        return "failed"

    if "success" in final_statuses:
        return "success"

    if "no_new_data" in final_statuses:
        return "no_new_data"

    return "empty"


def update_financial_indicators(
    symbols=None,
    start_year=None,
    limit=None,
    offset=0,
    sleep_seconds=DEFAULT_SLEEP_SECONDS,
    retries=DEFAULT_RETRIES,
    force_refresh=False,
    datasets=None,
):
    """批量更新股票基本财务数据。"""

    initialize_database()

    if start_year is None:
        start_year = DEFAULT_START_YEAR

    if datasets is None:
        datasets = DEFAULT_DATASETS

    datasets = tuple(datasets)

    if symbols is None:
        symbols = load_stock_universe_symbols()

    symbols = list(symbols)

    if offset:
        symbols = symbols[offset:]

    if limit is not None:
        symbols = symbols[:limit]

    if not symbols:
        print("stock_universe 中没有可更新的股票")
        return

    print(
        f"准备更新 {len(symbols)} 只股票的财务数据，"
        f"数据集: {','.join(datasets)}，"
        f"起始年份: {start_year}，"
        f"间隔: {sleep_seconds} 秒，"
        f"失败重试: {retries} 次，"
        f"强制刷新: {force_refresh}"
    )

    for index, symbol in enumerate(symbols, start=1):
        print(f"[{index}/{len(symbols)}] 开始更新 {symbol}")

        update_symbol_with_retries(
            symbol=symbol,
            datasets=datasets,
            start_year=start_year,
            retries=retries,
            sleep_seconds=sleep_seconds,
            force_refresh=force_refresh,
        )

        if index < len(symbols):
            print(f"等待 {sleep_seconds} 秒后继续下一只股票")
            time.sleep(sleep_seconds)


def parse_dataset_arg(value):
    """解析 --datasets 参数。"""

    datasets = []

    for item in value.split(","):
        dataset = item.strip()

        if not dataset:
            continue

        if dataset not in DATASET_CONFIG:
            valid = ", ".join(DATASET_CONFIG)
            raise argparse.ArgumentTypeError(
                f"未知数据集 {dataset}; 可选值: {valid}"
            )

        datasets.append(dataset)

    if not datasets:
        raise argparse.ArgumentTypeError("至少选择一个数据集")

    return tuple(datasets)


def parse_args():
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="批量更新股票基本财务数据到 SQLite")

    parser.add_argument(
        "--symbol",
        action="append",
        help="只更新指定股票，可重复传入，例如 --symbol sh600519 --symbol sz000001",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=None,
        help="只保留该年份之后的财务指标和三大报表；默认从 2015 年开始",
    )
    parser.add_argument(
        "--datasets",
        type=parse_dataset_arg,
        default=DEFAULT_DATASETS,
        help=(
            "要更新的数据集，逗号分隔；"
            "可选 indicators,statements；默认全部"
        ),
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
        help="每只股票之间等待多少秒；默认 8 秒",
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
        help="即使本地已是最新，也重新写入已有记录，用于刷新字段口径",
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
        datasets=args.datasets,
    )
