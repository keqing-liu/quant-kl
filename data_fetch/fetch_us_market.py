"""美国股票和 ETF 历史行情下载函数。"""

import hashlib
import os
import re
import ssl
import time
from html.parser import HTMLParser
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
STOOQ_CSV_DOWNLOAD_URL = "https://stooq.com/q/d/l/"
STOOQ_HISTORY_URL = "https://stooq.com/q/d/"
STOOQ_DOWNLOAD_URL = STOOQ_CSV_DOWNLOAD_URL
STOOQ_VERIFY_URL = "https://stooq.com/__verify"
STOOQ_API_KEY_ENV = "STOOQ_API_KEY"
STOOQ_PAGE_DELAY_SECONDS = 2
STOOQ_INITIAL_HISTORY_MAX_PAGES = 10
STOOQ_CSV_DOWNLOAD_RETRIES = 3
STOOQ_CSV_DOWNLOAD_RETRY_DELAY_SECONDS = 2
STOOQ_EMPTY_PAGE_RETRIES = 3
STOOQ_EMPTY_PAGE_RETRY_DELAY_SECONDS = 5
STOOQ_SYMBOL_ALIASES = {
    "ndq": "^ndq",
}
STOOQ_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)


class _StooqHistoricalTableParser(HTMLParser):
    """解析 Stooq 历史行情页里的最新行情表格。"""

    def __init__(self):
        super().__init__()
        self.in_target_table = False
        self.in_cell = False
        self.current_row = None
        self.current_cell = []
        self.rows = []
        self._table_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag == "table":
            if attrs.get("id") == "fth1" and not self.in_target_table:
                self.in_target_table = True
                self._table_depth = 1
            elif self.in_target_table:
                self._table_depth += 1

        if not self.in_target_table:
            return

        if tag == "tr":
            self.current_row = []
        elif tag in {"td", "th"} and self.current_row is not None:
            self.in_cell = True
            self.current_cell = []

    def handle_data(self, data):
        if self.in_target_table and self.in_cell:
            self.current_cell.append(data)

    def handle_endtag(self, tag):
        if not self.in_target_table:
            return

        if tag in {"td", "th"} and self.in_cell:
            cell_text = " ".join("".join(self.current_cell).split())
            self.current_row.append(cell_text)
            self.in_cell = False
            self.current_cell = []
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self.in_target_table = False


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

    stooq_symbol = STOOQ_SYMBOL_ALIASES.get(stooq_symbol, stooq_symbol)

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


def _build_stooq_opener():
    """构造带 cookie 的 Stooq opener。"""

    handlers = [HTTPCookieProcessor(CookieJar())]
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())
        handlers.append(HTTPSHandler(context=context))

    return build_opener(*handlers)


def _is_stooq_browser_challenge(text):
    """判断 Stooq 是否返回了 JavaScript 浏览器验证页。"""

    return (
        "This site requires JavaScript to verify your browser" in text
        or "/__verify" in text
    )


def _is_stooq_manual_captcha(text):
    """判断 Stooq 是否返回了人工输入验证码页。"""

    return (
        "Rewrite the above code" in text
        or "Wrong code! Try again" in text
        or "/q/l/s/i/?" in text
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


def _parse_stooq_csv_text(csv_text):
    """解析 Stooq CSV 文本，返回 price_data 兼容字段。"""

    if _is_stooq_browser_challenge(csv_text):
        raise RuntimeError("Stooq 仍然返回浏览器验证页，无法下载 CSV")

    if "access denied" in csv_text.lower():
        raise RuntimeError("Stooq CSV 返回 Access denied")

    if "<html" in csv_text.lower() or "<!doctype html" in csv_text.lower():
        raise RuntimeError("Stooq 返回了 HTML 页面而不是 CSV")

    try:
        history = pd.read_csv(StringIO(csv_text))
    except pd.errors.EmptyDataError as exc:
        raise RuntimeError("Stooq CSV 为空") from exc

    if history is None or history.empty or "Date" not in history.columns:
        raise RuntimeError("Stooq CSV 缺少 Date 列或没有数据")

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
        raise RuntimeError(f"Stooq CSV 缺少字段: {missing_columns}")

    return df[PRICE_COLUMNS]


def _download_stooq_csv_once(opener, url):
    """尝试读取一次 Stooq CSV URL。"""

    csv_text = _read_stooq_url(opener, url)

    if _is_stooq_browser_challenge(csv_text):
        _pass_stooq_browser_challenge(opener, csv_text)
        csv_text = _read_stooq_url(opener, url)

    if "Get your apikey" in csv_text or "Uzyskaj apikey" in csv_text:
        raise RuntimeError("Stooq CSV 返回 apikey 提示页")

    return _parse_stooq_csv_text(csv_text)


def _download_stooq_csv(stooq_symbol):
    """用 Stooq CSV 下载日线行情，失败时重试。"""

    query = {
        "s": stooq_symbol,
        "i": "d",
    }
    api_key = os.environ.get(STOOQ_API_KEY_ENV)

    if api_key:
        query["apikey"] = api_key

    url = f"{STOOQ_DOWNLOAD_URL}?{urlencode(query)}"
    opener = _build_stooq_opener()
    last_error = None

    for attempt in range(1, STOOQ_CSV_DOWNLOAD_RETRIES + 1):
        try:
            return _download_stooq_csv_once(opener, url)
        except Exception as exc:
            last_error = exc

            if attempt < STOOQ_CSV_DOWNLOAD_RETRIES:
                time.sleep(STOOQ_CSV_DOWNLOAD_RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"Stooq CSV 下载失败，已重试 {STOOQ_CSV_DOWNLOAD_RETRIES} 次: {last_error}"
    )


def _build_stooq_history_url(stooq_symbol, page=None):
    """构造 Stooq 历史页 URL。"""

    query = {
        "s": stooq_symbol,
        "i": "d",
    }

    if page is not None and page > 1:
        query["l"] = page

    return f"{STOOQ_HISTORY_URL}?{urlencode(query)}"


def _read_stooq_history_html(opener, url):
    """读取 Stooq 历史页，并在必要时完成一次浏览器验证。"""

    html = _read_stooq_url(opener, url)

    if _is_stooq_browser_challenge(html):
        _pass_stooq_browser_challenge(opener, html)
        html = _read_stooq_url(opener, url)

    if _is_stooq_browser_challenge(html):
        raise RuntimeError("Stooq 仍然返回浏览器验证页，无法解析历史页")

    if _is_stooq_manual_captcha(html):
        raise RuntimeError(
            "Stooq 触发人工验证码，无法自动下载；请稍后重试或降低分页数量"
        )

    return html


def _extract_stooq_max_history_page(html):
    """从历史页分页链接中提取最大页码。"""

    page_numbers = [
        int(match)
        for match in re.findall(r"(?:[?&]|&amp;)l=(\d+)", html)
    ]

    if not page_numbers:
        return 1

    return max(page_numbers)


def _parse_stooq_history_html(html):
    """解析 Stooq 当前历史数据 HTML 页面里的最近日线行情。"""

    parser = _StooqHistoricalTableParser()
    parser.feed(html)

    rows = parser.rows
    if not rows:
        return _empty_price_frame()

    data_rows = []
    for row in rows:
        if len(row) < 9 or row[1].lower() == "date":
            continue

        data_rows.append({
            "date": row[1],
            "open": row[2],
            "high": row[3],
            "low": row[4],
            "close": row[5],
            "volume": row[8],
        })

    if not data_rows:
        return _empty_price_frame()

    df = pd.DataFrame(data_rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for column in ["open", "high", "low", "close"]:
        df[column] = pd.to_numeric(
            df[column].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )

    df["volume"] = pd.to_numeric(
        df["volume"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    ).fillna(0).astype("int64")

    df = df.dropna(subset=["date", "open", "high", "low", "close"])
    if df.empty:
        return _empty_price_frame()

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    return df[PRICE_COLUMNS].sort_values("date").reset_index(drop=True)


def _download_stooq_history_page(stooq_symbol, opener=None, page=1):
    """从 Stooq 当前历史页解析最近约 40 个交易日，用于日常增量更新。"""

    url = _build_stooq_history_url(stooq_symbol, page=page)

    try:
        if opener is None:
            opener = _build_stooq_opener()

        for attempt in range(1, STOOQ_EMPTY_PAGE_RETRIES + 1):
            html = _read_stooq_history_html(opener, url)
            df = _parse_stooq_history_html(html)

            if not df.empty or attempt == STOOQ_EMPTY_PAGE_RETRIES:
                return df

            time.sleep(STOOQ_EMPTY_PAGE_RETRY_DELAY_SECONDS)
    except Exception as exc:
        raise RuntimeError(f"Stooq 历史页下载失败: {exc}") from exc


def _download_stooq_full_history(stooq_symbol, max_pages=STOOQ_INITIAL_HISTORY_MAX_PAGES):
    """分页下载 Stooq 历史页；max_pages=None 表示下载所有分页。"""

    opener = _build_stooq_opener()
    first_url = _build_stooq_history_url(stooq_symbol)
    print(f"Stooq {stooq_symbol} 正在下载第 1 页")

    try:
        for attempt in range(1, STOOQ_EMPTY_PAGE_RETRIES + 1):
            first_html = _read_stooq_history_html(opener, first_url)
            first_df = _parse_stooq_history_html(first_html)

            if not first_df.empty or attempt == STOOQ_EMPTY_PAGE_RETRIES:
                break

            time.sleep(STOOQ_EMPTY_PAGE_RETRY_DELAY_SECONDS)
    except Exception as exc:
        raise RuntimeError(f"Stooq 初始历史页下载失败: {exc}") from exc

    if first_df.empty:
        raise RuntimeError("Stooq 第 1 页没有解析到数据")

    available_pages = _extract_stooq_max_history_page(first_html)
    if max_pages is None:
        max_page = available_pages
    else:
        max_page = min(available_pages, max_pages)

    frames = [first_df]

    for page in range(2, max_page + 1):
        if STOOQ_PAGE_DELAY_SECONDS > 0:
            time.sleep(STOOQ_PAGE_DELAY_SECONDS)

        print(f"Stooq {stooq_symbol} 正在下载第 {page}/{max_page} 页")

        try:
            page_df = _download_stooq_history_page(
                stooq_symbol,
                opener=opener,
                page=page,
            )
        except Exception as exc:
            raise RuntimeError(f"Stooq 第 {page} 页历史下载失败: {exc}") from exc

        if page_df.empty:
            raise RuntimeError(f"Stooq 第 {page} 页没有解析到数据")

        frames.append(page_df)

        if page == max_page:
            print(
                f"Stooq {stooq_symbol} 初始历史下载进度: "
                f"{page}/{max_page} 页（Stooq 共 {available_pages} 页）"
            )

    frames = [frame for frame in frames if frame is not None and not frame.empty]
    if not frames:
        return _empty_price_frame()

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["date"])

    return df[PRICE_COLUMNS].sort_values("date").reset_index(drop=True)


def _download_stooq_price_data(stooq_symbol, full_history=False, max_pages=STOOQ_INITIAL_HISTORY_MAX_PAGES):
    """用 Stooq 历史页表格下载行情，避免不稳定的 CSV 直链。"""

    if full_history:
        return _download_stooq_full_history(stooq_symbol, max_pages=max_pages)

    return _download_stooq_history_page(stooq_symbol)


def download_us_market_data(symbol, full_history=False, max_pages=STOOQ_INITIAL_HISTORY_MAX_PAGES):
    """用 Stooq 下载美国市场日线行情，返回 price_data 兼容字段。"""

    return _download_stooq_price_data(
        build_stooq_symbol(symbol),
        full_history=full_history,
        max_pages=max_pages,
    )


def download_stooq_data(symbol, full_history=False, max_pages=STOOQ_INITIAL_HISTORY_MAX_PAGES):
    """用 Stooq 原始符号下载指数/指标日线行情。"""

    return _download_stooq_price_data(
        normalize_stooq_symbol(symbol),
        full_history=full_history,
        max_pages=max_pages,
    )
