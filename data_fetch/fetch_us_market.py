"""美国股票和 ETF 历史行情下载函数。"""

import os
import re
from io import StringIO
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd


PRICE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
STOOQ_DOWNLOAD_URL = "https://stooq.com/q/d/l/"
STOOQ_API_KEY_ENV = "STOOQ_API_KEY"


def normalize_us_ticker(symbol):
    """把内部 us_xxx symbol 或原始 ticker 转成美国市场 ticker。"""

    ticker = str(symbol).strip()

    if ticker.lower().startswith("us_"):
        ticker = ticker[3:]

    ticker = ticker.replace("_", "-").upper()

    if not re.fullmatch(r"[A-Z0-9.-]+", ticker):
        raise ValueError(f"无法识别美国市场 ticker: {symbol}")

    return ticker


def build_us_symbol(ticker):
    """把美国市场 ticker 转成项目内部 us_xxx symbol。"""

    normalized = normalize_us_ticker(ticker).lower().replace("-", "_").replace(".", "_")

    return f"us_{normalized}"


def build_stooq_symbol(ticker):
    """把美国市场 ticker 转成 Stooq 下载符号，例如 AAPL -> aapl.us。"""

    return f"{normalize_us_ticker(ticker).lower()}.us"


def normalize_stooq_symbol(symbol):
    """规范化 Stooq 原始符号，例如 ^vix、^sox。"""

    stooq_symbol = str(symbol).strip().lower()

    if stooq_symbol.startswith("stooq_"):
        stooq_symbol = f"^{stooq_symbol[6:]}"

    if not re.fullmatch(r"\^?[a-z0-9._-]+", stooq_symbol):
        raise ValueError(f"无法识别 Stooq symbol: {symbol}")

    return stooq_symbol


def build_stooq_internal_symbol(symbol):
    """把 Stooq 原始符号转成项目内部 symbol，例如 ^vix -> stooq_vix。"""

    stooq_symbol = normalize_stooq_symbol(symbol)
    normalized = stooq_symbol.lstrip("^").replace("-", "_").replace(".", "_")

    return f"stooq_{normalized}"


def _empty_price_frame():
    """返回 price_data 兼容的空行情表。"""

    return pd.DataFrame(columns=PRICE_COLUMNS)


def _download_stooq_csv(stooq_symbol):
    """用 Stooq CSV 下载日线行情，返回 price_data 兼容字段。"""

    query = {
        "s": stooq_symbol,
        "i": "d",
    }
    api_key = os.environ.get(STOOQ_API_KEY_ENV)

    if api_key:
        query["apikey"] = api_key

    url = f"{STOOQ_DOWNLOAD_URL}?{urlencode(query)}"

    try:
        request = Request(url, headers={"User-Agent": "quant-kl/1.0"})
        with urlopen(request, timeout=30) as response:
            csv_text = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"Stooq 行情下载失败: {exc}") from exc

    if "Get your apikey" in csv_text or "Uzyskaj apikey" in csv_text:
        raise RuntimeError(
            "Stooq CSV 下载需要 STOOQ_API_KEY。请先在 Stooq 获取免费 apikey，"
            "再执行 export STOOQ_API_KEY='你的key'"
        )

    try:
        history = pd.read_csv(StringIO(csv_text))
    except pd.errors.EmptyDataError:
        return _empty_price_frame()

    if history is None or history.empty or "Date" not in history.columns:
        return _empty_price_frame()

    df = history.rename(
        columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )

    missing_columns = [column for column in PRICE_COLUMNS if column not in df.columns]
    if missing_columns:
        return _empty_price_frame()

    return df[PRICE_COLUMNS]


def download_us_market_data(symbol):
    """用 Stooq CSV 下载美国市场日线行情，返回 price_data 兼容字段。"""

    return _download_stooq_csv(build_stooq_symbol(symbol))


def download_stooq_data(symbol):
    """用 Stooq 原始符号下载指数/指标日线行情。"""

    return _download_stooq_csv(normalize_stooq_symbol(symbol))
