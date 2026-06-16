"""从 SQLite 数据库读取最近几天/几周的技术指标，并打印成摘要表。

这个脚本主要用于快速查看每个 ETF / 股票最近的技术指标状态。

数据来源：
1. price_data 表：保存原始行情数据，例如 close
2. indicators 表：保存已经计算好的技术指标
3. weekly_price_data 表：保存周线行情数据
4. weekly_indicators 表：保存已经计算好的周线技术指标
"""

import argparse

import pandas as pd

from config.watchlist import WATCHLIST
from database.db_utils import get_connection
from data_fetch.fetch_cboe_market import build_cboe_index_internal_symbol
from data_fetch.fetch_us_market import build_stooq_internal_symbol, build_us_symbol


# =========================
# 读取数据库中的所有 symbol
# =========================

def get_frequency_tables(frequency):
    if frequency == "daily":
        return "price_data", "indicators", "交易日"

    if frequency == "weekly":
        return "weekly_price_data", "weekly_indicators", "周线"

    raise ValueError(f"不支持的 frequency: {frequency}")


def get_all_symbols(frequency="daily"):

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    _price_table, indicator_table, _period_label = get_frequency_tables(frequency)

    # 从 indicators 表中找出所有已经计算过指标的 symbol。
    df = pd.read_sql(f"""
        SELECT DISTINCT symbol
        FROM {indicator_table}
        ORDER BY symbol
    """, conn)

    conn.close()

    # 转成普通 Python 列表，方便后面循环。
    return df["symbol"].tolist()


# =========================
# 读取单个 symbol 的摘要数据
# =========================

def load_summary_data(symbol, days=5, frequency="daily"):

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    price_table, indicator_table, _period_label = get_frequency_tables(frequency)

    # 从 indicators 表读取技术指标。
    # 同时 JOIN price_data 表读取 close 收盘价。
    #
    # JOIN 条件：
    # symbol 和 date 都相同。
    #
    # ORDER BY i.date DESC：
    # 先按日期从新到旧排序。
    #
    # LIMIT ?：
    # 只读取最近 N 个交易日。
    df = pd.read_sql(f"""
        SELECT
            i.date,
            p.close,

            i.VOL5,
            i.VOL20,

            i.MA20,
            i.MA60,

            i.BOLL_UPPER,
            i.BOLL_LOWER,

            i.K,
            i.D,
            i.J,

            i.CCI

        FROM {indicator_table} AS i

        JOIN {price_table} AS p
        ON i.symbol = p.symbol
        AND i.date = p.date

        WHERE i.symbol = ?

        ORDER BY i.date DESC

        LIMIT ?
    """, conn, params=(symbol, days))

    conn.close()

    return df


def load_price_summary_data(symbol, days=5, frequency="daily"):

    # VIX / VXN 这类市场风险指标只保存在 price_data。
    # 它们本身就是指标，所以不会写入 indicators 表。
    # 因此这里单独读取 OHLC，而不是 JOIN indicators。
    conn = get_connection()

    price_table, _indicator_table, _period_label = get_frequency_tables(frequency)

    df = pd.read_sql(f"""
        SELECT
            date,
            open,
            high,
            low,
            close,
            volume

        FROM {price_table}

        WHERE symbol = ?

        ORDER BY date DESC

        LIMIT ?
    """, conn, params=(symbol, days))

    conn.close()

    return df


def build_group_symbols(group):

    # CLI 里的 --group 是给人看的分组名称。
    # 数据库里保存的是内部 symbol，所以这里负责把分组转换成可查询的 symbol 列表。
    #
    # 例如：
    # WATCHLIST["US_ETF"] 里的 "QQQ" 入库时会变成 "us_qqq"；
    # WATCHLIST["US_MARKET_INDICATOR"] 里的 "^vix" 入库时会变成 "cboe_vix"。
    if group == "cn-etf":
        return WATCHLIST.get("ETF", [])

    if group == "cn-stock":
        return WATCHLIST.get("STOCK", [])

    if group == "us-etf":
        return [
            build_us_symbol(ticker)
            for ticker in WATCHLIST.get("US_ETF", [])
        ]

    if group == "us-stock":
        return [
            build_us_symbol(ticker)
            for ticker in WATCHLIST.get("US_STOCK", [])
        ]

    if group == "us-index":
        return [
            build_stooq_internal_symbol(symbol)
            for symbol in WATCHLIST.get("US_INDEX", [])
        ]

    if group == "us-market-indicator":
        return [
            build_cboe_index_internal_symbol(symbol)
            for symbol in WATCHLIST.get("US_MARKET_INDICATOR", [])
        ]

    if group == "us-risk":
        risk_symbols = []

        # us-risk 是一个人为定义的风险监控组合：
        # 用 QQQ 看 Nasdaq-100 / 科技成长风险，
        # 用 SMH 看半导体风险，
        # 再加 Cboe 的 VIX / VXN 看隐含波动率风险。
        for ticker in WATCHLIST.get("US_ETF", []):
            normalized = ticker.upper()
            if normalized in {"QQQ", "SMH"}:
                risk_symbols.append(build_us_symbol(normalized))

        risk_symbols.extend(
            build_cboe_index_internal_symbol(symbol)
            for symbol in WATCHLIST.get("US_MARKET_INDICATOR", [])
        )

        if "stooq_sox" in get_all_price_symbols():
            risk_symbols.append("stooq_sox")

        return risk_symbols

    if group == "all":
        return get_all_symbols()

    raise ValueError(f"未知分组: {group}")


def get_market_indicator_symbols():

    # 这组 symbol 用来判断某个标的是不是“市场风险指标”。
    # 如果是，就只打印价格序列；如果不是，就打印技术指标摘要。
    return {
        build_cboe_index_internal_symbol(symbol)
        for symbol in WATCHLIST.get("US_MARKET_INDICATOR", [])
    }


def get_all_price_symbols():

    conn = get_connection()

    df = pd.read_sql("""
        SELECT DISTINCT symbol
        FROM price_data
        ORDER BY symbol
    """, conn)

    conn.close()

    return df["symbol"].tolist()


# =========================
# 输出单个 ETF / 股票摘要
# =========================

def print_summary(symbol, days=5, frequency="daily"):

    _price_table, _indicator_table, period_label = get_frequency_tables(frequency)
    print("\n")
    print("=" * 80)
    print(f"{symbol} 最近{days}个{period_label}技术指标")
    print("=" * 80)

    # 从 SQLite 读取最近 5 天数据。
    recent = load_summary_data(symbol, days=days, frequency=frequency)

    # 如果没有数据，直接提示并返回。
    if recent.empty:
        if frequency == "weekly":
            print(f"{symbol} 没有周线指标数据，请先运行 python -m quant e weekly")
        else:
            print(f"{symbol} 没有指标数据，请先运行 indicator.py")
        return

    # 把字符串日期转为 datetime，方便格式化。
    recent["date"] = pd.to_datetime(recent["date"])

    # 因为 SQL 已经 ORDER BY date DESC，
    # 所以这里默认最新日期在最上面。
    #
    # 如果你想按从旧到新显示，可以取消下一行注释：
    # recent = recent.sort_values("date")

    # 只展示最关心的列，避免终端输出太宽。
    columns = [
        "date",
        "close",
        "VOL5",
        "VOL20",
        "MA20",
        "MA60",
        "BOLL_UPPER",
        "BOLL_LOWER",
        "K",
        "D",
        "J",
        "CCI"
    ]

    # 选择需要显示的列。
    recent = recent[columns]

    # 日期格式化为 YYYY-MM-DD，输出更清晰。
    recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")

    # round(2) 对数值列保留两位小数。
    recent = recent.round(2)

    # to_string(index=False) 打印表格时隐藏 pandas 自动行号。
    print(recent.to_string(index=False))


def print_price_summary(symbol, days=5, frequency="daily"):

    _price_table, _indicator_table, period_label = get_frequency_tables(frequency)
    print("\n")
    print("=" * 80)
    print(f"{symbol} 最近{days}个{period_label}价格序列")
    print("=" * 80)

    recent = load_price_summary_data(symbol, days=days, frequency=frequency)

    if recent.empty:
        if frequency == "weekly":
            print(f"{symbol} 没有周线价格数据，请先运行 python -m quant e weekly")
        else:
            print(f"{symbol} 没有价格数据，请先运行 main.py")
        return

    recent["date"] = pd.to_datetime(recent["date"]).dt.strftime("%Y-%m-%d")

    columns = [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    recent = recent[columns].round(2)

    print(recent.to_string(index=False))


# =========================
# 批量输出所有 symbol 摘要
# =========================

def run_summary(symbols=None, group="all", days=5, frequency="daily"):

    # --symbols 优先级最高：用户手动指定时，就不再理会 --group。
    # 如果没有 --symbols，才根据 --group 从 watchlist 里推导 symbol。
    if symbols:
        selected_symbols = symbols
    else:
        if group == "all":
            selected_symbols = get_all_symbols(frequency=frequency)
        else:
            selected_symbols = build_group_symbols(group)

    if not selected_symbols:
        print("没有找到要输出的 symbol，请检查分组或 watchlist")
        return

    market_indicator_symbols = get_market_indicator_symbols()

    for symbol in selected_symbols:

        try:

            # VIX / VXN 没有技术指标记录，所以走 price_data 输出。
            # ETF / 股票已经由 analysis.indicators 写入 indicators，所以走技术指标输出。
            if symbol in market_indicator_symbols:
                print_price_summary(symbol, days=days, frequency=frequency)
            else:
                print_summary(symbol, days=days, frequency=frequency)

        except Exception as e:

            # 单个 symbol 出错时只打印错误，不影响其他 symbol 继续输出。
            print(f"{symbol} 输出失败: {e}")


def parse_args():

    # argparse 会把终端里的参数解析成 Python 对象。
    # 例如：
    # python -m analysis.summary --group us-risk --days 5
    # 会得到 args.group == "us-risk"，args.days == 5。
    parser = argparse.ArgumentParser(
        description="按分组或 symbol 输出最近 N 天价格/技术指标摘要"
    )

    parser.add_argument(
        "--group",
        choices=[
            "all",
            "cn-etf",
            "cn-stock",
            "us-etf",
            "us-stock",
            "us-index",
            "us-market-indicator",
            "us-risk",
        ],
        default="all",
        help="要输出的 watchlist 分组；默认输出所有已有技术指标的 symbol",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="输出最近几个交易日/几根周线；默认 5",
    )

    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly"],
        default="daily",
        help="摘要频率；daily 读取日线表，weekly 读取周线表；默认 daily",
    )

    parser.add_argument(
        "--symbols",
        nargs="+",
        help="手动指定内部 symbol，优先级高于 --group，例如 sh510310 us_qqq cboe_vix",
    )

    return parser.parse_args()


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    args = parse_args()
    run_summary(
        symbols=args.symbols,
        group=args.group,
        days=args.days,
        frequency=args.frequency,
    )
