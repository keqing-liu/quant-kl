"""从 SQLite 数据库读取 ETF / 股票行情，并使用 mplfinance 绘制 K 线图。

mplfinance 要求：
1. 日期列作为 index
2. OHLCV 列名必须是：
   Open / High / Low / Close / Volume
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MPL_CACHE_DIR = Path("/private/tmp/quant_kl_matplotlib_cache")
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE_DIR))
os.environ.setdefault("XDG_CACHE_HOME", str(MPL_CACHE_DIR))

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import mplfinance as mpf

from config.watchlist import WATCHLIST
from database.db_utils import get_connection
from data_fetch.fetch_us_market import build_us_symbol


# =========================
# 从 SQLite 读取行情数据
# =========================

def load_price_data(symbol, months=None):

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    # 如果传入 months，就先找到该 symbol 的最新日期，
    # 再从最新日期往前推 N 个月作为起点。
    # 这样即使数据库不是今天刚更新，也能稳定画“最近 N 个月”。
    start_date = None
    if months is not None:
        latest_date = pd.read_sql("""
            SELECT MAX(date) AS latest_date
            FROM price_data
            WHERE symbol = ?
        """, conn, params=(symbol,))["latest_date"].iloc[0]

        if latest_date is None:
            conn.close()
            return pd.DataFrame()

        start_date = (
            pd.to_datetime(latest_date) - pd.DateOffset(months=months)
        ).strftime("%Y-%m-%d")

    # 从 price_data 表读取指定 symbol 的历史行情。
    # ORDER BY date 保证时间从旧到新排序。
    if start_date is None:
        df = pd.read_sql("""

            SELECT *
            FROM price_data
            WHERE symbol = ?
            ORDER BY date

        """, conn, params=(symbol,))
    else:
        df = pd.read_sql("""

            SELECT *
            FROM price_data
            WHERE symbol = ?
              AND date >= ?
            ORDER BY date

        """, conn, params=(symbol, start_date))

    conn.close()

    return df


def build_group_symbols(group):
    """把命令行里的分组名称转换成数据库内部 symbol 列表。"""

    if group == "cn-etf":
        return WATCHLIST.get("ETF", [])

    if group == "us-etf":
        return [
            build_us_symbol(ticker)
            for ticker in WATCHLIST.get("US_ETF", [])
        ]

    if group == "us-risk":
        symbols = []

        for ticker in WATCHLIST.get("US_ETF", []):
            normalized = ticker.upper()
            if normalized in {"QQQ", "SMH"}:
                symbols.append(build_us_symbol(normalized))

        return symbols

    raise ValueError(f"未知 ETF 分组: {group}")


def resolve_symbols(symbols=None, group=None):
    """决定本次要画哪些 symbol。手动 --symbols 优先于 --group。"""

    if symbols:
        return symbols

    if group:
        return build_group_symbols(group)

    return ["sh510310"]


# =========================
# 绘制 K 线图
# =========================

def plot_etf(symbol, months=None, output_path=None):

    print(f"开始绘制 {symbol} K线图...")

    # 从数据库读取数据。
    df = load_price_data(symbol, months=months)

    # DataFrame 为空时直接返回，避免后面绘图报错。
    if df.empty:

        print(f"{symbol} 没有数据")

        return

    # SQLite 中 date 通常保存为文本；
    # 转成 datetime 后才能作为时间索引。
    df["date"] = pd.to_datetime(df["date"])

    # 设置日期为 index。
    # mplfinance 要求时间序列 index 必须是 DatetimeIndex。
    df.set_index("date", inplace=True)

    # mplfinance 识别的是标准 OHLCV 英文列名。
    df.rename(columns={

        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume"

    }, inplace=True)

    # =========================
    # 绘制蜡烛图
    # =========================

    plot_kwargs = {
        # candle = K线图
        "type": "candle",

        # 显示成交量子图
        "volume": True,

        # 均线
        "mav": (20, 60),

        # 图标题
        "title": f"{symbol} Candlestick Chart",

        # 使用 Yahoo 风格配色
        "style": "yahoo",

        # 图像大小
        "figsize": (12, 8),
    }

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        plot_kwargs["savefig"] = dict(fname=output_file, dpi=150, bbox_inches="tight")

    mpf.plot(df, **plot_kwargs)

    if output_path:
        print(f"图像已保存到: {output_path}")

    print(f"{symbol} K线图绘制完成")


def build_output_path(output, symbol, multiple_symbols):
    """多标的画图时，自动把 symbol 加到文件名里，避免互相覆盖。"""

    if output is None:
        return None

    output_path = Path(output)

    if not multiple_symbols:
        return output_path

    suffix = output_path.suffix or ".png"
    stem = output_path.stem if output_path.suffix else output_path.name

    return output_path.with_name(f"{stem}_{symbol}{suffix}")


def parse_args():

    parser = argparse.ArgumentParser(
        description="从 price_data 绘制 ETF / 股票 K 线、成交量和均线图。"
    )

    parser.add_argument(
        "--months",
        type=int,
        help="回看月份数，例如 --months 18；默认读取该 symbol 的全部历史。",
    )

    parser.add_argument(
        "--symbol",
        dest="single_symbols",
        action="append",
        help="要绘制的内部 symbol，可重复使用，例如 --symbol sh510310 --symbol us_qqq。",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        help="一次指定多个内部 symbol，例如 --symbols sh510310 us_qqq us_smh。",
    )

    parser.add_argument(
        "--group",
        choices=[
            "cn-etf",
            "us-etf",
            "us-risk",
        ],
        help="按 watchlist 分组绘图；如果同时传 --symbols/--symbol，则手动 symbol 优先。",
    )

    parser.add_argument(
        "--output",
        help="可选：保存图片路径，例如 data/etf_recent_18m.png。多标的时会自动追加 symbol。",
    )

    return parser.parse_args()


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    args = parse_args()
    cli_symbols = []
    if args.single_symbols:
        cli_symbols.extend(args.single_symbols)
    if args.symbols:
        cli_symbols.extend(args.symbols)

    selected_symbols = resolve_symbols(
        symbols=cli_symbols or None,
        group=args.group,
    )
    multiple_symbols = len(selected_symbols) > 1

    for symbol in selected_symbols:
        output_path = build_output_path(args.output, symbol, multiple_symbols)
        plot_etf(
            symbol=symbol,
            months=args.months,
            output_path=output_path,
        )
