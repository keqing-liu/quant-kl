"""美国股票和 ETF 历史行情下载函数。"""

import hashlib
import os
import re
import ssl
from http.cookiejar import CookieJar
from io import StringIO
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, HTTPCookieProcessor, Request, build_opener

import pandas as pd

try:
    import certifi
except ImportError:
    certifi = None


PRICE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
STOOQ_DOWNLOAD_URL = "https://stooq.com/q/d/l/"
STOOQ_VERIFY_URL = "https://stooq.com/__verify"
STOOQ_API_KEY_ENV = "STOOQ_API_KEY"
STOOQ_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)


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


def _build_stooq_request(url, data=None, headers=None):
    """构造 Stooq 请求，尽量模拟普通浏览器访问。"""

    request_headers = {
        "User-Agent": STOOQ_USER_AGENT,
        "Accept": "text/csv,text/plain,text/html,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    if headers:
        request_headers.update(headers)

    return Request(url, data=data, headers=request_headers)


def _read_stooq_url(opener, url, data=None, headers=None):
    """读取 Stooq URL 并返回文本内容。"""

    request = _build_stooq_request(url, data=data, headers=headers)

    with opener.open(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _is_stooq_browser_challenge(text):
    """判断 Stooq 是否返回了 JavaScript 浏览器验证页。"""

    return (
        "This site requires JavaScript to verify your browser" in text
        or "/__verify" in text
    )


def _extract_stooq_challenge(text):
    """从 Stooq 验证页中提取 proof-of-work challenge。"""

    match = re.search(
        r'const\s+c="([^"]+)",d=(\d+)',
        text,
        flags=re.DOTALL,
    )

    if not match:
        raise RuntimeError("无法解析 Stooq 浏览器验证参数")

    return match.group(1), int(match.group(2))


def _solve_stooq_challenge(challenge, difficulty):
    """计算 Stooq JavaScript 验证页要求的 nonce。"""

    prefix = "0" * difficulty
    nonce = 0
    max_nonce = 10_000_000

    while nonce < max_nonce:
        digest = hashlib.sha256(
            f"{challenge}{nonce}".encode("utf-8")
        ).hexdigest()

        if digest.startswith(prefix):
            return nonce

        nonce += 1

    raise RuntimeError("Stooq 浏览器验证计算超时")


def _pass_stooq_browser_challenge(opener, challenge_text):
    """模拟浏览器完成 Stooq /__verify 验证并保存 cookie。"""

    challenge, difficulty = _extract_stooq_challenge(challenge_text)
    nonce = _solve_stooq_challenge(challenge, difficulty)
    body = urlencode({"c": challenge, "n": nonce}).encode("utf-8")

    _read_stooq_url(
        opener,
        STOOQ_VERIFY_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://stooq.com",
            "Referer": STOOQ_DOWNLOAD_URL,
        },
    )


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
        handlers = [HTTPCookieProcessor(CookieJar())]
        if certifi is not None:
            context = ssl.create_default_context(cafile=certifi.where())
            handlers.append(HTTPSHandler(context=context))

        opener = build_opener(*handlers)
        csv_text = _read_stooq_url(opener, url)

        if _is_stooq_browser_challenge(csv_text):
            _pass_stooq_browser_challenge(opener, csv_text)
            csv_text = _read_stooq_url(opener, url)
    except Exception as exc:
        raise RuntimeError(f"Stooq 行情下载失败: {exc}") from exc

    if _is_stooq_browser_challenge(csv_text):
        raise RuntimeError("Stooq 仍然返回浏览器验证页，无法下载 CSV")

    if "Get your apikey" in csv_text or "Uzyskaj apikey" in csv_text:
        raise RuntimeError(
            "Stooq CSV 下载需要 STOOQ_API_KEY。请先在 Stooq 获取免费 apikey，"
            "再执行 export STOOQ_API_KEY='你的key'"
        )

    if "<html" in csv_text.lower() or "<!doctype html" in csv_text.lower():
        raise RuntimeError("Stooq 返回了 HTML 页面而不是 CSV，请检查 apikey 或登录验证状态")

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
