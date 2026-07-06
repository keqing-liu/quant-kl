"""EODHD 多伦多交易所股票日度行情下载函数。

EODHD 的加拿大多伦多交易所代码使用 `.TO` 后缀，例如 Royal Bank of
Canada 是 RY.TO，Toronto-Dominion Bank 是 TD.TO。不要使用裸代码 RY / TD，
因为裸代码会返回美股上市价格。
"""

import json
import os
import re
import ssl
from datetime import date, timedelta
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd

try:
    import certifi
except ImportError:
    certifi = None


PRICE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
EODHD_EOD_URL = "https://eodhd.com/api/eod"
EODHD_API_KEY_ENV = "EODHD_API_KEY"
EODHD_DEFAULT_HISTORY_YEARS = 5
EODHD_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)


def normalize_eodhd_ca_symbol(symbol):
    """规范化 EODHD 多伦多股票代码，例如 RY.TO、TD.TO。"""

    normalized = str(symbol).strip().upper()

    if normalized.startswith("CA_"):
        normalized = normalized[3:].replace("_", ".")

    if "." not in normalized:
        normalized = f"{normalized}.TO"

    if not normalized.endswith(".TO"):
        raise ValueError(
            f"EODHD 加拿大股票必须使用多伦多交易所 .TO 后缀: {symbol}"
        )

    if not re.fullmatch(r"[A-Z0-9.-]+\.TO", normalized):
        raise ValueError(f"无法识别 EODHD 加拿大股票 symbol: {symbol}")

    return normalized


def build_ca_stock_symbol(symbol):
    """把 EODHD ticker 转成项目内部 symbol，例如 RY.TO -> ca_ry_to。"""

    normalized = normalize_eodhd_ca_symbol(symbol)
    return f"ca_{normalized.lower().replace('.', '_').replace('-', '_')}"


def get_eodhd_default_start_date():
    """返回 EODHD 默认下载起点。"""

    return (date.today() - timedelta(days=365 * EODHD_DEFAULT_HISTORY_YEARS)).strftime(
        "%Y-%m-%d"
    )


def _normalize_date_string(value, field_name):
    if value is None:
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"无法识别 {field_name}: {value}")

    return parsed.strftime("%Y-%m-%d")


def _empty_price_frame():
    """返回 price_data 兼容的空行情表。"""

    return pd.DataFrame(columns=PRICE_COLUMNS)


def _build_eodhd_eod_url(symbol, start_date=None, end_date=None):
    normalized = normalize_eodhd_ca_symbol(symbol)
    query = {
        "fmt": "json",
        "period": "d",
    }

    normalized_start_date = _normalize_date_string(start_date, "EODHD start_date")
    normalized_end_date = _normalize_date_string(end_date, "EODHD end_date")

    if normalized_start_date:
        query["from"] = normalized_start_date

    if normalized_end_date:
        query["to"] = normalized_end_date

    return f"{EODHD_EOD_URL}/{quote(normalized, safe='')}?{urlencode(query)}"


def _read_eodhd_url(url):
    api_key = os.environ.get(EODHD_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(f"缺少 {EODHD_API_KEY_ENV}，无法使用 EODHD 下载股票")

    separator = "&" if "?" in url else "?"
    request_url = f"{url}{separator}{urlencode({'api_token': api_key})}"

    request = Request(
        request_url,
        headers={
            "User-Agent": EODHD_USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    context = None
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())

    with urlopen(request, timeout=30, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def _parse_eodhd_eod_json(text, adjust_prices=True):
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("EODHD 返回内容不是有效 JSON") from exc

    if isinstance(payload, dict):
        detail = payload.get("message") or payload.get("error") or payload
        raise RuntimeError(f"EODHD 返回错误: {detail}")

    if not payload:
        return _empty_price_frame()

    df = pd.DataFrame(payload)
    missing_columns = [
        column
        for column in ["date", "open", "high", "low", "close"]
        if column not in df.columns
    ]
    if missing_columns:
        raise RuntimeError(f"EODHD 数据缺少字段: {missing_columns}")

    if adjust_prices and "adjusted_close" in df.columns:
        close = pd.to_numeric(df["close"], errors="coerce")
        adjusted_close = pd.to_numeric(df["adjusted_close"], errors="coerce")
        factor = adjusted_close / close
        factor = factor.replace([float("inf"), float("-inf")], pd.NA).fillna(1)
        for column in ["open", "high", "low", "close"]:
            df[column] = pd.to_numeric(df[column], errors="coerce") * factor

    if "volume" not in df.columns:
        df["volume"] = 0

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    df = df.dropna(subset=["date", "open", "high", "low", "close"])

    if df.empty:
        return _empty_price_frame()

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    return df[PRICE_COLUMNS].sort_values("date").reset_index(drop=True)


def download_eodhd_ca_stock_data(
    symbol,
    start_date=None,
    end_date=None,
    adjust_prices=True,
):
    """用 EODHD 下载多伦多交易所股票日线行情。"""

    url = _build_eodhd_eod_url(
        symbol,
        start_date=start_date or get_eodhd_default_start_date(),
        end_date=end_date,
    )
    text = _read_eodhd_url(url)

    return _parse_eodhd_eod_json(text, adjust_prices=adjust_prices)
