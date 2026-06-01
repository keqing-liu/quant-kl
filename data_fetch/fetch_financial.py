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
    "revenue",
    "revenue_yoy",
    "net_profit",
    "net_profit_yoy",
    "gross_margin",
    "debt_ratio",
    "operating_cash_flow",
    "eps",
    "data_source",
]


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
    result["gross_margin"] = _get_numeric_column(
        df,
        [
            "销售毛利率(%)",
            "XSMLL",
        ],
    )
    result["debt_ratio"] = _get_numeric_column(
        df,
        [
            "资产负债率(%)",
            "ZCFZL",
        ],
    )
    result["operating_cash_flow"] = _get_numeric_column(
        df,
        [
            "经营现金净流量与净利润的比率(%)",
            "每股经营性现金流(元)",
            "经营活动产生的现金流量净额",
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


def _normalize_internal_symbol(symbol):
    """把 6 位股票代码补成项目内部使用的 sh/sz 前缀格式。"""

    stock_code = normalize_stock_code(symbol)

    if stock_code.startswith("6"):
        return f"sh{stock_code}"

    return f"sz{stock_code}"


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


def _get_pandas():
    """延迟导入 pandas，避免模块导入阶段就要求依赖齐全。"""

    import pandas as pd

    return pd


def _empty_raw_financial_indicators():
    """返回空的原始财务指标表。"""

    pd = _get_pandas()

    return pd.DataFrame()
