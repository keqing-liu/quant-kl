"""Alpha Vantage 加拿大股票日度行情下载函数。"""

import json
import os
import re
import ssl
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

try:
    import certifi
except ImportError:
    certifi = None


PRICE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
ALPHA_VANTAGE_QUERY_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_API_KEY_ENV = "ALPHA_VANTAGE_API_KEY"
ALPHA_VANTAGE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)


def normalize_alpha_vantage_ca_symbol(symbol):
    """规范化 Alpha Vantage 加拿大股票 symbol，例如 RY.TRT。"""

    normalized = str(symbol).strip().upper()

    if normalized.startswith("CA_"):
        normalized = normalized[3:].replace("_", ".")

    if not re.fullmatch(r"[A-Z0-9.-]+", normalized):
        raise ValueError(f"无法识别 Alpha Vantage 加拿大股票 symbol: {symbol}")

    return normalized


def build_ca_stock_symbol(symbol):
    """把加拿大股票 symbol 转成项目内部 symbol，例如 RY.TRT -> ca_ry_trt。"""

    normalized = normalize_alpha_vantage_ca_symbol(symbol)
    return f"ca_{normalized.lower().replace('.', '_').replace('-', '_')}"


def _empty_price_frame():
    """返回 price_data 兼容的空行情表。"""

    return pd.DataFrame(columns=PRICE_COLUMNS)


def _build_alpha_vantage_daily_url(symbol, outputsize="compact"):
    api_key = os.environ.get(ALPHA_VANTAGE_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"缺少 {ALPHA_VANTAGE_API_KEY_ENV}，无法使用 Alpha Vantage 下载加拿大股票"
        )

    query = {
        "function": "TIME_SERIES_DAILY",
        "symbol": normalize_alpha_vantage_ca_symbol(symbol),
        "outputsize": outputsize,
        "apikey": api_key,
    }

    return f"{ALPHA_VANTAGE_QUERY_URL}?{urlencode(query)}"


def _read_alpha_vantage_url(url):
    request = Request(
        url,
        headers={
            "User-Agent": ALPHA_VANTAGE_USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    context = None
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())

    with urlopen(request, timeout=30, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_alpha_vantage_daily_json(text):
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Alpha Vantage 返回内容不是有效 JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Alpha Vantage 返回内容格式异常")

    for key in ["Error Message", "Information", "Note"]:
        if payload.get(key):
            raise RuntimeError(f"Alpha Vantage 返回错误: {payload[key]}")

    time_series = payload.get("Time Series (Daily)")
    if not time_series:
        return _empty_price_frame()

    rows = []
    for date_value, values in time_series.items():
        rows.append(
            {
                "date": date_value,
                "open": values.get("1. open"),
                "high": values.get("2. high"),
                "low": values.get("3. low"),
                "close": values.get("4. close"),
                "volume": values.get("5. volume", 0),
            }
        )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    df = df.dropna(subset=["date", "open", "high", "low", "close"])

    if df.empty:
        return _empty_price_frame()

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df[PRICE_COLUMNS].sort_values("date").reset_index(drop=True)


def download_alpha_vantage_ca_stock_data(symbol, outputsize="compact"):
    """用 Alpha Vantage 下载加拿大股票日线行情。"""

    url = _build_alpha_vantage_daily_url(symbol, outputsize=outputsize)
    text = _read_alpha_vantage_url(url)

    return _parse_alpha_vantage_daily_json(text)
