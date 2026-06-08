"""Cboe 市场风险指标日度数据下载函数。"""

import re
import ssl
from io import StringIO
from urllib.request import Request, urlopen

import pandas as pd

try:
    import certifi
except ImportError:
    certifi = None


PRICE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
CBOE_DAILY_PRICES_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
CBOE_INDEX_FILES = {
    "vix": "VIX_History.csv",
    "vxn": "VXN_History.csv",
    "vvix": "VVIX_History.csv",
    "skew": "SKEW_History.csv",
}


def normalize_cboe_index_symbol(symbol):
    """规范化 Cboe 指标符号，例如 ^vix、cboe_vix、VIX。"""

    index_symbol = str(symbol).strip().lower()

    if index_symbol.startswith("cboe_"):
        index_symbol = index_symbol[5:]

    index_symbol = index_symbol.lstrip("^")

    if not re.fullmatch(r"[a-z0-9._-]+", index_symbol):
        raise ValueError(f"无法识别 Cboe index symbol: {symbol}")

    if index_symbol not in CBOE_INDEX_FILES:
        raise ValueError(f"暂不支持的 Cboe index symbol: {symbol}")

    return index_symbol


def build_cboe_index_internal_symbol(symbol):
    """把 Cboe 指标转成项目内部 symbol，例如 ^vix -> cboe_vix。"""

    return f"cboe_{normalize_cboe_index_symbol(symbol)}"


def _empty_price_frame():
    """返回 price_data 兼容的空行情表。"""

    return pd.DataFrame(columns=PRICE_COLUMNS)


def download_cboe_index_data(symbol):
    """下载 Cboe 日度指数数据，返回 price_data 兼容字段。"""

    index_symbol = normalize_cboe_index_symbol(symbol)
    file_name = CBOE_INDEX_FILES[index_symbol]
    url = f"{CBOE_DAILY_PRICES_URL}/{file_name}"

    try:
        request = Request(url, headers={"User-Agent": "quant-kl/1.0"})
        context = None
        if certifi is not None:
            context = ssl.create_default_context(cafile=certifi.where())

        with urlopen(request, timeout=30, context=context) as response:
            csv_text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"Cboe 指标下载失败: {exc}") from exc

    try:
        history = pd.read_csv(StringIO(csv_text))
    except pd.errors.EmptyDataError:
        return _empty_price_frame()

    if history is None or history.empty or "DATE" not in history.columns:
        return _empty_price_frame()

    value_column = index_symbol.upper()
    if value_column in history.columns and "CLOSE" not in history.columns:
        history["OPEN"] = history[value_column]
        history["HIGH"] = history[value_column]
        history["LOW"] = history[value_column]
        history["CLOSE"] = history[value_column]

    df = history.rename(
        columns={
            "DATE": "date",
            "OPEN": "open",
            "HIGH": "high",
            "LOW": "low",
            "CLOSE": "close",
        }
    )

    missing_columns = [column for column in PRICE_COLUMNS[:-1] if column not in df.columns]
    if missing_columns:
        return _empty_price_frame()

    df["volume"] = 0

    return df[PRICE_COLUMNS]
