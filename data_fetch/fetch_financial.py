"""单只 A 股财务指标下载与整理函数。

本模块只负责下载和清洗，不负责写入 SQLite。
后续批量更新脚本可以复用 download_financial_indicators() 的结果。
"""

import re
from datetime import date


FINANCIAL_COLUMNS = [
    # 这个列表是“下载清洗结果”和 financial_indicators 表之间的字段契约。
    # update_financial_data.py 会按这个顺序把 DataFrame 写入 SQLite。
    # 如果以后增删财务字段，要同步修改：
    # 1. 这里的 FINANCIAL_COLUMNS；
    # 2. standardize_financial_indicators() 的字段生成逻辑；
    # 3. database/schema/base.sql；
    # 4. database/migrations/00N_*.sql；
    # 5. update_financial_data.py 中的 INSERT / UPDATE SQL。
    "symbol",
    "report_date",
    "announce_date",
    "period_type",
    "fiscal_year",
    "fiscal_period",
    "roe",
    "weighted_roe",
    "roa",
    "revenue",
    "revenue_yoy",
    "net_profit",
    "net_profit_yoy",
    "deducted_net_profit",
    "gross_margin",
    "operating_margin",
    "net_margin",
    "cost_expense_margin",
    "main_profit_ratio",
    "non_main_ratio",
    "debt_ratio",
    "equity_ratio",
    "current_ratio",
    "quick_ratio",
    "cash_ratio",
    "interest_coverage",
    "receivable_turnover",
    "receivable_days",
    "inventory_turnover",
    "inventory_days",
    "total_asset_turnover",
    "fixed_asset_ratio",
    "ocf_to_revenue",
    "ocf_to_net_profit",
    "ocf_to_debt",
    "cash_flow_ratio",
    "operating_cash_flow",
    "operating_cash_flow_per_share",
    "book_value_per_share",
    "eps",
    "data_source",
]

# financial_indicators 表字段说明：
# symbol: 项目内部股票代码，例如 sh600519 / sz000001。
# report_date: 财报报告期日期，来自新浪财务指标“日期”。
# announce_date: 公告日；新浪财务指标端口通常不提供，当前保留为 NULL。
# period_type: 报告期类型；当前统一为 report。
# fiscal_year / fiscal_period: 从 report_date 推导出的会计年度和季度。
# roe: 净资产收益率(%)，优先取“净资产收益率(%)”。
# weighted_roe: 加权净资产收益率(%)。
# roa: 总资产净利润率/总资产利润率/资产报酬率(%)。
# revenue: 营业收入；新浪财务指标端口通常缺该绝对金额，更多依赖三大报表。
# revenue_yoy: 主营业务收入增长率(%)。
# net_profit: 净利润；该指标端口缺净利润时会用扣非净利润候选补位。
# net_profit_yoy: 净利润增长率(%)。
# deducted_net_profit: 扣除非经常性损益后的净利润(元)。
# gross_margin: 销售毛利率(%)；部分股票该字段可能为空。
# operating_margin: 营业利润率(%)。
# net_margin: 销售净利率(%)。
# cost_expense_margin: 成本费用利润率(%)。
# main_profit_ratio: 主营利润比重。
# non_main_ratio: 非主营比重。
# debt_ratio: 资产负债率(%)。
# equity_ratio: 股东权益比率(%)。
# current_ratio / quick_ratio: 流动比率 / 速动比率。
# cash_ratio: 现金比率(%)。
# interest_coverage: 利息支付倍数。
# receivable_turnover / receivable_days: 应收账款周转率(次) / 周转天数(天)。
# inventory_turnover / inventory_days: 存货周转率(次) / 周转天数(天)。
# total_asset_turnover: 总资产周转率(次)。
# fixed_asset_ratio: 固定资产比重(%)。
# ocf_to_revenue: 经营现金净流量对销售收入比率(%)。
# ocf_to_net_profit: 经营现金净流量与净利润的比率(%)。
# ocf_to_debt: 经营现金净流量对负债比率(%)。
# cash_flow_ratio: 现金流量比率(%)。
# operating_cash_flow: 经营现金流相关绝对值；若端口没有绝对值，可能退化为每股经营现金流。
# operating_cash_flow_per_share: 每股经营性现金流(元)。
# book_value_per_share: 每股净资产(元)。
# eps: 摊薄/加权每股收益(元)。
# data_source: 数据来源标识。


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

# financial_statement_items 表字段说明：
# 这张表保存新浪三大报表原始项目的“窄表”结构，不把所有报表科目硬编码成列。
# symbol: 项目内部股票代码。
# report_date: 报告期日期，来自新浪三大报表“报告日”。
# announce_date: 公告日期，来自新浪三大报表“公告日期”。
# statement_type: 报表类型，取值为“利润表”“资产负债表”“现金流量表”。
# item_name: 原始报表科目名，例如“营业总收入”“资产总计”“经营活动产生的现金流量净额”。
# item_value: 报表科目数值，通常为元。
# currency: 币种。
# report_type: 新浪返回的报表类型，例如“合并期末”。
# is_audited: 是否审计。
# data_source: 数据来源标识。


def normalize_stock_code(symbol):
    """把系统内部 symbol 转成 AkShare 财务接口需要的 6 位股票代码。"""

    if symbol is None:
        raise ValueError("symbol 不能为空")

    stock_code = str(symbol).strip().lower()

    if stock_code.startswith(("sh", "sz")):
        stock_code = stock_code[2:]

    if not re.fullmatch(r"\d{6}", stock_code):
        raise ValueError(
            f"无法识别股票代码: {symbol}; 期望格式如 sh600519、sz000001 或 600519"
        )

    return stock_code


def download_raw_financial_indicators(symbol, start_year=None):
    """下载 AkShare 原始财务指标数据。"""

    import akshare as ak

    stock_code = normalize_stock_code(symbol)

    if start_year is None:
        start_year = date.today().year - 10

    start_year = int(start_year)

    # 新浪接口要求 start_year 必须出现在该股票的年份列表中。
    # 新上市公司可能没有 10 年前的数据，所以这里从 start_year 开始逐年往后试。
    # 这样全市场批量更新时，不会因为某只新股缺少早期年份而中断。
    for candidate_year in range(start_year, date.today().year + 1):
        try:
            df = ak.stock_financial_analysis_indicator(
                symbol=stock_code,
                start_year=str(candidate_year),
            )
        except AttributeError as e:
            if "'NoneType' object has no attribute 'find'" not in str(e):
                raise

            continue

        if df is not None and not df.empty:
            return df

    return _empty_raw_financial_indicators()


def download_financial_indicators(symbol, start_year=None):
    """下载并整理单只股票财务指标，返回适配 financial_indicators 表的 DataFrame。"""

    raw_df = download_raw_financial_indicators(
        symbol=symbol,
        start_year=start_year,
    )

    return standardize_financial_indicators(
        raw_df=raw_df,
        symbol=symbol,
        start_year=start_year,
    )


def download_financial_statements(symbol, start_year=None):
    """下载新浪三大报表，并整理成窄表 item 结构。"""

    import akshare as ak

    stock = _normalize_sina_stock_symbol(symbol)
    frames = []

    for statement_type in ("利润表", "资产负债表", "现金流量表"):
        raw_df = ak.stock_financial_report_sina(
            stock=stock,
            symbol=statement_type,
        )
        df = standardize_financial_statement(
            raw_df=raw_df,
            symbol=symbol,
            statement_type=statement_type,
            start_year=start_year,
        )
        if not df.empty:
            frames.append(df)

    pd = _get_pandas()

    if not frames:
        return pd.DataFrame(columns=STATEMENT_COLUMNS)

    return pd.concat(frames, ignore_index=True)


def standardize_financial_indicators(raw_df, symbol, start_year=None):
    """把 AkShare 财务指标字段整理成项目统一字段。"""

    pd = _get_pandas()

    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=FINANCIAL_COLUMNS)

    df = raw_df.copy()

    # AkShare 不同版本或不同接口返回的列名可能不完全一致。
    # 因此这里为关键字段准备多个候选列名，取第一个实际存在的列。
    report_date_column = _find_first_column(
        df,
        [
            "REPORT_DATE",
            "日期",
        ],
    )

    if report_date_column is None:
        raise ValueError("AkShare 财务指标结果缺少报告日期字段")

    result = pd.DataFrame(index=df.index)

    result["symbol"] = _normalize_internal_symbol(symbol)
    result["report_date"] = pd.to_datetime(
        df[report_date_column],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    # 当前 AkShare 这个接口主要返回报告期，并不稳定提供公告日。
    # 先保留 announce_date 字段为空，方便以后接入公告日接口后补齐。
    # 做历史回测时应优先使用 announce_date，而不是 report_date。
    result["announce_date"] = None
    result["period_type"] = "report"
    report_dates = pd.to_datetime(
        result["report_date"],
        errors="coerce",
    )
    result["fiscal_year"] = report_dates.dt.year
    result["fiscal_period"] = "Q" + report_dates.dt.quarter.astype("string")

    # 下面每个字段都使用“候选列名列表”。
    # 这样即使 AkShare 字段名从中文变成英文缩写，代码也有一定兼容性。
    result["roe"] = _get_numeric_column(
        df,
        [
            "净资产收益率(%)",
            "加权净资产收益率(%)",
            "ROEJQ",
        ],
    )
    result["weighted_roe"] = _get_numeric_column(
        df,
        [
            "加权净资产收益率(%)",
        ],
    )
    result["roa"] = _get_numeric_column(
        df,
        [
            "总资产净利润率(%)",
            "总资产利润率(%)",
            "资产报酬率(%)",
        ],
    )
    result["revenue"] = _get_numeric_column(
        df,
        [
            "营业总收入",
            "主营业务收入",
        ],
    )
    result["revenue_yoy"] = _get_numeric_column(
        df,
        [
            "主营业务收入增长率(%)",
            "营业总收入同比增长率(%)",
            "TOTALOPERATEREVETZ",
        ],
    )
    result["net_profit"] = _get_numeric_column(
        df,
        [
            "净利润",
            "归属于母公司所有者的净利润",
            "扣除非经常性损益后的净利润(元)",
        ],
    )
    result["net_profit_yoy"] = _get_numeric_column(
        df,
        [
            "净利润增长率(%)",
            "归属于母公司所有者的净利润同比增长率(%)",
            "PARENTNETPROFITTZ",
        ],
    )
    result["deducted_net_profit"] = _get_numeric_column(
        df,
        [
            "扣除非经常性损益后的净利润(元)",
        ],
    )
    result["gross_margin"] = _get_numeric_column(
        df,
        [
            "销售毛利率(%)",
            "XSMLL",
        ],
    )
    result["operating_margin"] = _get_numeric_column(
        df,
        [
            "营业利润率(%)",
        ],
    )
    result["net_margin"] = _get_numeric_column(
        df,
        [
            "销售净利率(%)",
        ],
    )
    result["cost_expense_margin"] = _get_numeric_column(
        df,
        [
            "成本费用利润率(%)",
        ],
    )
    result["main_profit_ratio"] = _get_numeric_column(
        df,
        [
            "主营利润比重",
        ],
    )
    result["non_main_ratio"] = _get_numeric_column(
        df,
        [
            "非主营比重",
        ],
    )
    result["debt_ratio"] = _get_numeric_column(
        df,
        [
            "资产负债率(%)",
            "ZCFZL",
        ],
    )
    result["equity_ratio"] = _get_numeric_column(
        df,
        [
            "股东权益比率(%)",
        ],
    )
    result["current_ratio"] = _get_numeric_column(df, ["流动比率"])
    result["quick_ratio"] = _get_numeric_column(df, ["速动比率"])
    result["cash_ratio"] = _get_numeric_column(df, ["现金比率(%)"])
    result["interest_coverage"] = _get_numeric_column(df, ["利息支付倍数"])
    result["receivable_turnover"] = _get_numeric_column(
        df,
        ["应收账款周转率(次)"],
    )
    result["receivable_days"] = _get_numeric_column(
        df,
        ["应收账款周转天数(天)"],
    )
    result["inventory_turnover"] = _get_numeric_column(df, ["存货周转率(次)"])
    result["inventory_days"] = _get_numeric_column(df, ["存货周转天数(天)"])
    result["total_asset_turnover"] = _get_numeric_column(
        df,
        ["总资产周转率(次)"],
    )
    result["fixed_asset_ratio"] = _get_numeric_column(df, ["固定资产比重(%)"])
    result["ocf_to_revenue"] = _get_numeric_column(
        df,
        ["经营现金净流量对销售收入比率(%)"],
    )
    result["ocf_to_net_profit"] = _get_numeric_column(
        df,
        ["经营现金净流量与净利润的比率(%)"],
    )
    result["ocf_to_debt"] = _get_numeric_column(
        df,
        ["经营现金净流量对负债比率(%)"],
    )
    result["cash_flow_ratio"] = _get_numeric_column(df, ["现金流量比率(%)"])
    result["operating_cash_flow"] = _get_numeric_column(
        df,
        [
            "经营活动产生的现金流量净额",
            "经营现金净流量",
            "每股经营性现金流(元)",
        ],
    )
    result["operating_cash_flow_per_share"] = _get_numeric_column(
        df,
        [
            "每股经营性现金流(元)",
        ],
    )
    result["book_value_per_share"] = _get_numeric_column(
        df,
        [
            "每股净资产_调整后(元)",
            "每股净资产_调整前(元)",
            "调整后的每股净资产(元)",
        ],
    )
    result["eps"] = _get_numeric_column(
        df,
        [
            "摊薄每股收益(元)",
            "加权每股收益(元)",
            "EPSJB",
        ],
    )
    result["data_source"] = "akshare_sina_financial_indicator"

    # report_date 是 financial_indicators 的主键之一，缺失时无法落库。
    result = result.dropna(subset=["report_date"])

    if start_year is not None:
        result = result[result["fiscal_year"] >= int(start_year)]

    # 同一股票同一报告期只保留一条，避免 upsert 时出现同批次重复主键。
    result = result.drop_duplicates(
        subset=["symbol", "report_date"],
    )
    result = result.sort_values("report_date").reset_index(drop=True)

    return result[FINANCIAL_COLUMNS]


def standardize_financial_statement(raw_df, symbol, statement_type, start_year=None):
    """把新浪三大报表转成 symbol/report_date/item_name/item_value 窄表。"""

    pd = _get_pandas()

    if raw_df is None or raw_df.empty:
        return pd.DataFrame(columns=STATEMENT_COLUMNS)

    df = raw_df.copy()
    report_date_column = _find_first_column(df, ["报告日", "REPORT_DATE"])

    if report_date_column is None:
        raise ValueError(f"{statement_type} 缺少报告日期字段")

    meta_columns = {
        report_date_column,
        "数据源",
        "是否审计",
        "公告日期",
        "币种",
        "类型",
        "更新日期",
    }
    value_columns = [column for column in df.columns if column not in meta_columns]
    records = []
    internal_symbol = _normalize_internal_symbol(symbol)

    for _, row in df.iterrows():
        report_date = _format_date(row.get(report_date_column), compact=True)

        if report_date is None:
            continue

        fiscal_year = int(report_date[:4])

        if start_year is not None and fiscal_year < int(start_year):
            continue

        announce_date = _format_date(row.get("公告日期"), compact=True)

        for item_name in value_columns:
            item_value = _to_float(row.get(item_name))

            if item_value is None:
                continue

            records.append(
                {
                    "symbol": internal_symbol,
                    "report_date": report_date,
                    "announce_date": announce_date,
                    "statement_type": statement_type,
                    "item_name": str(item_name),
                    "item_value": item_value,
                    "currency": _clean_text_value(row.get("币种")),
                    "report_type": _clean_text_value(row.get("类型")),
                    "is_audited": _clean_text_value(row.get("是否审计")),
                    "data_source": "akshare_sina_financial_report",
                }
            )

    if not records:
        return pd.DataFrame(columns=STATEMENT_COLUMNS)

    result = pd.DataFrame(records)
    result = result.drop_duplicates(
        subset=["symbol", "report_date", "statement_type", "item_name"],
    )
    result = result.sort_values(
        ["symbol", "report_date", "statement_type", "item_name"],
    ).reset_index(drop=True)

    return result[STATEMENT_COLUMNS]


def _normalize_internal_symbol(symbol):
    """把 6 位股票代码补成项目内部使用的 sh/sz 前缀格式。"""

    stock_code = normalize_stock_code(symbol)

    if stock_code.startswith("6"):
        return f"sh{stock_code}"

    return f"sz{stock_code}"


def _normalize_sina_stock_symbol(symbol):
    """把内部 symbol 转成新浪三大报表使用的 sh/sz + 6 位代码。"""

    internal_symbol = _normalize_internal_symbol(symbol)

    return internal_symbol


def _get_numeric_column(df, candidate_columns):
    """按候选列名取第一个存在的字段，并转成数值。"""

    column = _find_first_column(df, candidate_columns)

    if column is not None:
        return _to_numeric(df[column])

    return None


def _find_first_column(df, candidate_columns):
    """从候选字段中找到第一个实际存在的列名。"""

    for column in candidate_columns:
        if column in df.columns:
            return column

    return None


def _get_series(df, column_name):
    """安全读取一列；缺列时返回与 df 等长的空列。"""

    pd = _get_pandas()

    if column_name in df.columns:
        return df[column_name]

    return pd.Series([None] * len(df), index=df.index)


def _to_numeric(series):
    """把 AkShare 返回的字符串数字转成 float，无法转换的值记为缺失。"""

    pd = _get_pandas()

    # AkShare 常见返回值包括 "1,234.56"、"12.3%"、"--"、"-"。
    # 统一清洗后再交给 pandas 转数值，可以减少后续分析里的特殊判断。
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
        .replace(
            {
                "--": None,
                "-": None,
                "": None,
                "nan": None,
                "None": None,
            }
        )
    )

    return pd.to_numeric(cleaned, errors="coerce")


def _to_float(value):
    """把单个值清洗成 float。"""

    if value is None:
        return None

    text = str(value).replace(",", "").replace("%", "").strip()

    if not text or text.lower() in ("nan", "none", "nat") or text in ("--", "-"):
        return None

    try:
        return float(text)
    except ValueError:
        return None


def _format_date(value, compact=False):
    """把 AkShare 日期值整理成 YYYY-MM-DD。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in ("nan", "none", "nat"):
        return None

    if compact and re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"

    pd = _get_pandas()
    parsed = pd.to_datetime(text, errors="coerce")

    if pd.isna(parsed):
        return None

    return parsed.strftime("%Y-%m-%d")


def _clean_text_value(value):
    """清洗可选文本值。"""

    if value is None:
        return None

    text = str(value).strip()

    if not text or text.lower() in ("nan", "none", "nat"):
        return None

    return text


def _get_pandas():
    """延迟导入 pandas，避免模块导入阶段就要求依赖齐全。"""

    import pandas as pd

    return pd


def _empty_raw_financial_indicators():
    """返回空的原始财务指标表。"""

    pd = _get_pandas()

    return pd.DataFrame()
