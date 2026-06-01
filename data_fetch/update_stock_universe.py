"""同步沪深 A 股股票名单到 stock_universe 表。

本脚本使用 AkShare 的交易所股票列表接口，不使用东方财富接口。

运行方式：

    python3 -m data_fetch.update_stock_universe
"""

from database.db_utils import (
    get_connection,
    initialize_database,
    log_data_update,
)


DATA_SOURCE = "akshare_exchange_stock_info"

# 上交所接口需要按板块分别请求；深交所接口使用一个 A 股列表入口。
# 把这些接口参数集中成常量，后续如果 AkShare 改参数名，修改位置更集中。
SH_INDICATORS = ["主板A股", "科创板"]
SZ_INDICATOR = "A股列表"


def download_stock_universe():
    """下载沪深 A 股股票名单，并整理成 stock_universe 表需要的记录。"""

    # 延迟导入 akshare，可以让单元测试或只读数据库工具在没有 akshare 时也能导入本模块。
    import akshare as ak

    records = []

    for indicator in SH_INDICATORS:
        # 上交所主板和科创板分开取，再统一整理成 stock_universe 的内部字段。
        df = ak.stock_info_sh_name_code(symbol=indicator)
        records.extend(_normalize_sh_records(df))

    # 深交所接口字段名和上交所不同，所以单独写 normalize 函数。
    sz_df = ak.stock_info_sz_name_code(symbol=SZ_INDICATOR)
    records.extend(_normalize_sz_records(sz_df))

    return _deduplicate_records(records)


def _normalize_sh_records(df):
    """整理上交所股票列表字段。"""

    records = []

    for row in df.to_dict("records"):
        stock_code = _clean_stock_code(
            row.get("证券代码") or row.get("代码") or row.get("公司代码")
        )
        name = _clean_text(
            row.get("证券简称") or row.get("简称") or row.get("公司简称")
        )

        if stock_code is None or name is None:
            continue

        records.append(
            _build_stock_record(
                stock_code=stock_code,
                name=name,
                exchange="SH",
                list_date=row.get("上市日期"),
            )
        )

    return records


def _normalize_sz_records(df):
    """整理深交所股票列表字段。"""

    records = []

    for row in df.to_dict("records"):
        stock_code = _clean_stock_code(row.get("A股代码"))
        name = _clean_text(row.get("A股简称"))

        if stock_code is None or name is None:
            continue

        records.append(
            _build_stock_record(
                stock_code=stock_code,
                name=name,
                exchange="SZ",
                list_date=row.get("A股上市日期"),
            )
        )

    return records


def _build_stock_record(stock_code, name, exchange, list_date):
    """构造一条 stock_universe 记录。"""

    # stock_universe 是后续财报下载的入口表。
    # 这里只保存“股票是否值得进入后续流程”的基础状态，不保存行情或财报明细。
    return {
        "symbol": _build_symbol(stock_code, exchange),
        "stock_code": stock_code,
        "name": name,
        "exchange": exchange,
        "market": "CN",
        "is_active": 1,
        "is_st": _is_st_stock(name),
        "is_delisting_risk": _is_delisting_risk_stock(name),
        "list_date": _clean_date(list_date),
        "delist_date": None,
        "data_source": DATA_SOURCE,
        "note": None,
    }


def _build_symbol(stock_code, exchange):
    """把交易所和 6 位代码转换成项目内部 symbol。"""

    # 项目内部统一使用 sh600519 / sz000001 这种格式，
    # 和 fetch_stock.py 里的日线行情 symbol 保持一致。
    prefix = exchange.lower()

    return f"{prefix}{stock_code}"


def _is_st_stock(name):
    """根据股票简称判断是否 ST。"""

    # 这里是轻量级文本判断，不追求交易所状态的绝对完备。
    # 目的是在全市场财报筛选前，先过滤明显不适合的股票。
    upper_name = name.upper()

    if "ST" in upper_name:
        return 1

    return 0


def _is_delisting_risk_stock(name):
    """根据股票简称判断是否存在退市风险。"""

    upper_name = name.upper()

    if "*ST" in upper_name or "退" in name:
        return 1

    return 0


def _clean_stock_code(value):
    """把股票代码整理成 6 位字符串。"""

    if value is None:
        return None

    stock_code = str(value).strip()

    # 有些接口或 pandas 转换后会把代码变成 600519.0。
    # 写入数据库前统一还原成 6 位字符串。
    if stock_code.endswith(".0"):
        stock_code = stock_code[:-2]

    stock_code = stock_code.zfill(6)

    if len(stock_code) != 6 or not stock_code.isdigit():
        return None

    return stock_code


def _clean_text(value):
    """清洗文本字段。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def _clean_date(value):
    """把日期字段整理成 YYYY-MM-DD 文本。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in ("nat", "nan", "none"):
        return None

    return text[:10]


def _deduplicate_records(records):
    """按 symbol 去重，保留最后一条记录。"""

    record_map = {}

    for record in records:
        record_map[record["symbol"]] = record

    return list(record_map.values())


def save_stock_universe(records):
    """把股票名单写入 stock_universe 表。"""

    if not records:
        return 0

    conn = get_connection()

    try:
        cursor = conn.cursor()

        # 先把沪深旧股票标记为非活跃，再把本次下载到的股票重新标记为活跃。
        # 这样如果某只股票从交易所当前列表消失，表里会保留记录但 is_active 会变成 0。
        # 这种做法比直接删除旧记录更适合研究系统：历史数据和日志仍然能追溯。
        cursor.execute(
            """
            UPDATE stock_universe
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE exchange IN ('SH', 'SZ')
            """
        )

        # ON CONFLICT(symbol) 做 upsert：
        # 新股票插入，已有股票更新名称、状态、上市日期等基础信息。
        sql = """
        INSERT INTO stock_universe (
            symbol,
            stock_code,
            name,
            exchange,
            market,
            is_active,
            is_st,
            is_delisting_risk,
            list_date,
            delist_date,
            data_source,
            note
        )
        VALUES (
            :symbol,
            :stock_code,
            :name,
            :exchange,
            :market,
            :is_active,
            :is_st,
            :is_delisting_risk,
            :list_date,
            :delist_date,
            :data_source,
            :note
        )
        ON CONFLICT(symbol)
        DO UPDATE SET
            stock_code = excluded.stock_code,
            name = excluded.name,
            exchange = excluded.exchange,
            market = excluded.market,
            is_active = excluded.is_active,
            is_st = excluded.is_st,
            is_delisting_risk = excluded.is_delisting_risk,
            list_date = excluded.list_date,
            delist_date = excluded.delist_date,
            data_source = excluded.data_source,
            note = excluded.note,
            updated_at = CURRENT_TIMESTAMP
        """

        cursor.executemany(sql, records)
        rows_saved = cursor.rowcount

        conn.commit()

        return rows_saved

    finally:
        conn.close()


def update_stock_universe():
    """同步沪深 A 股股票名单，并记录更新日志。"""

    # 先初始化数据库，确保 stock_universe 和 data_update_log 表存在。
    initialize_database()

    rows_downloaded = 0
    rows_saved = 0

    try:
        records = download_stock_universe()
        rows_downloaded = len(records)

        rows_saved = save_stock_universe(records)

        log_data_update(
            symbol="stock_universe",
            asset_type="STOCK_UNIVERSE",
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="success",
            message="沪深 A 股股票池同步成功",
            data_source=DATA_SOURCE,
        )

        print(
            "stock_universe 同步完成："
            f"下载 {rows_downloaded} 只股票，写入/更新 {rows_saved} 条记录"
        )

    except Exception as e:
        log_data_update(
            symbol="stock_universe",
            asset_type="STOCK_UNIVERSE",
            rows_downloaded=rows_downloaded,
            rows_inserted=rows_saved,
            status="failed",
            message=str(e),
            data_source=DATA_SOURCE,
        )

        print(f"stock_universe 同步失败: {e}")


if __name__ == "__main__":
    update_stock_universe()
