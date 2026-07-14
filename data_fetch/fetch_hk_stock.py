"""港股日线行情下载函数。

使用 AkShare 的 stock_hk_daily 新浪免费接口下载港股历史行情，并统一整理成
price_data 需要的 date/open/high/low/close/volume 字段。
"""


def build_hk_stock_symbol(symbol):
    """把港股代码转换为项目内部 symbol，例如 00700 -> hk_00700。"""

    normalized = str(symbol).strip().lower()
    if normalized.startswith("hk_"):
        code = normalized[3:]
    elif normalized.endswith(".hk"):
        code = normalized[:-3]
    elif normalized.startswith("hk"):
        code = normalized[2:]
    else:
        code = normalized

    code = code.zfill(5)
    return f"hk_{code}"


def build_akshare_hk_symbol(symbol):
    """把项目内部 symbol 转为 AkShare 港股代码，例如 hk_00700 -> 00700。"""

    return build_hk_stock_symbol(symbol).replace("hk_", "", 1)


def normalize_hk_stock_data(raw_df):
    """把 AkShare 港股字段标准化为项目统一行情字段。"""

    if raw_df is None or raw_df.empty:
        return raw_df

    rename_map = {
        "日期": "date",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
        "Date": "date",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }

    df = raw_df.rename(columns=rename_map).copy()
    required_columns = ["date", "open", "high", "low", "close", "volume"]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"AkShare 港股数据缺少字段: {missing}")

    df = df[required_columns].copy()
    df["date"] = df["date"].astype(str)

    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = df[column].astype(str).str.replace(",", "", regex=False)
        df[column] = df[column].replace({"": None, "nan": None, "None": None})
        df[column] = df[column].astype(float)

    return df


def download_hk_stock_data(symbol):
    """下载单只港股的前复权日线行情。"""

    import akshare as ak

    hk_symbol = build_akshare_hk_symbol(symbol)
    df = ak.stock_hk_daily(
        symbol=hk_symbol,
        adjust="qfq",
    )

    return normalize_hk_stock_data(df)
