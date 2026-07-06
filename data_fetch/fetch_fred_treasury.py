"""FRED 美国国债收益率日度数据下载函数。"""

import re
import shutil
import ssl
import subprocess
from datetime import date, timedelta
from io import StringIO
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

try:
    import certifi
except ImportError:
    certifi = None


PRICE_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_DEFAULT_HISTORY_YEARS = 5
FRED_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)
FRED_TREASURY_SERIES = {
    "DGS10": "10Y 美债收益率",
    "DGS2": "2Y 美债收益率",
}
FRED_TREASURY_SPREAD_SYMBOL = "fred_t10y2y"


def normalize_fred_treasury_series(series_id):
    """规范化 FRED 美债收益率序列 ID。"""

    normalized = str(series_id).strip().upper()

    if normalized.startswith("FRED_"):
        normalized = normalized[5:]

    if not re.fullmatch(r"[A-Z0-9_]+", normalized):
        raise ValueError(f"无法识别 FRED series_id: {series_id}")

    if normalized not in FRED_TREASURY_SERIES:
        raise ValueError(f"暂不支持的 FRED Treasury series_id: {series_id}")

    return normalized


def build_fred_treasury_internal_symbol(series_id):
    """把 FRED 序列转成项目内部 symbol，例如 DGS10 -> fred_dgs10。"""

    return f"fred_{normalize_fred_treasury_series(series_id).lower()}"


def get_fred_treasury_symbols():
    """返回当前支持的 FRED 美债收益率内部 symbol。"""

    return {
        build_fred_treasury_internal_symbol(series_id)
        for series_id in FRED_TREASURY_SERIES
    } | {FRED_TREASURY_SPREAD_SYMBOL}


def _empty_price_frame():
    """返回 price_data 兼容的空行情表。"""

    return pd.DataFrame(columns=PRICE_COLUMNS)


def get_fred_default_start_date():
    """返回 FRED 默认下载起点。"""

    return (date.today() - timedelta(days=365 * FRED_DEFAULT_HISTORY_YEARS)).strftime(
        "%Y-%m-%d"
    )


def _normalize_date_string(value, field_name):
    if value is None:
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"无法识别 {field_name}: {value}")

    return parsed.strftime("%Y-%m-%d")


def _build_fred_csv_url(series_id, start_date=None, end_date=None):
    query_params = {"id": series_id}
    normalized_start_date = _normalize_date_string(start_date, "FRED start_date")
    normalized_end_date = _normalize_date_string(end_date, "FRED end_date")

    if normalized_start_date:
        query_params["cosd"] = normalized_start_date

    if normalized_end_date:
        query_params["coed"] = normalized_end_date

    query = urlencode(query_params)
    return f"{FRED_GRAPH_CSV_URL}?{query}"


def _read_fred_csv_with_curl(url):
    curl_path = shutil.which("curl")
    if curl_path is None:
        raise RuntimeError("找不到 curl，无法使用 curl 下载 FRED CSV")

    result = subprocess.run(
        [
            curl_path,
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            "60",
            url,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or f"curl exit code {result.returncode}"
        raise RuntimeError(message)

    return result.stdout


def _read_fred_csv_with_urllib(url):
    request = Request(
        url,
        headers={
            "User-Agent": FRED_USER_AGENT,
            "Accept": "text/csv,text/plain,*/*",
        },
    )
    context = None
    if certifi is not None:
        context = ssl.create_default_context(cafile=certifi.where())

    with urlopen(request, timeout=30, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def _read_fred_csv(series_id, start_date=None, end_date=None):
    url = _build_fred_csv_url(
        series_id,
        start_date=start_date,
        end_date=end_date,
    )

    if shutil.which("curl") is not None:
        return _read_fred_csv_with_curl(url)

    return _read_fred_csv_with_urllib(url)


def download_fred_treasury_data(series_id, start_date=None, end_date=None):
    """下载 FRED 美债收益率数据，返回 price_data 兼容字段。"""

    normalized = normalize_fred_treasury_series(series_id)

    try:
        csv_text = _read_fred_csv(
            normalized,
            start_date=start_date or get_fred_default_start_date(),
            end_date=end_date,
        )
    except Exception as exc:
        raise RuntimeError(f"FRED 美债收益率下载失败: {exc}") from exc

    try:
        history = pd.read_csv(StringIO(csv_text))
    except pd.errors.EmptyDataError:
        return _empty_price_frame()

    if history is None or history.empty:
        return _empty_price_frame()

    date_column = "DATE" if "DATE" in history.columns else "observation_date"
    if date_column not in history.columns:
        return _empty_price_frame()

    value_column = normalized if normalized in history.columns else "VALUE"
    if value_column not in history.columns:
        return _empty_price_frame()

    df = history[[date_column, value_column]].rename(
        columns={
            date_column: "date",
            value_column: "close",
        }
    )
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "close"]).reset_index(drop=True)

    if df.empty:
        return _empty_price_frame()

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df["open"] = df["close"]
    df["high"] = df["close"]
    df["low"] = df["close"]
    df["volume"] = 0

    return df[PRICE_COLUMNS]
