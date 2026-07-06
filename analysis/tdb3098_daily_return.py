"""估算 TD Science & Technology Fund - D (TDB3098) 的单日涨跌幅。

用法示例：

    python -m analysis.tdb3098_daily_return \
        --date 2026-06-24 \
        --samsung-return 1.2 \
        --sk-hynix-return -0.8

说明：
- samsung-return / sk-hynix-return 一律输入百分比数值，例如 1.2 表示上涨 1.2%。
- 例如 -0.8 表示下跌 0.8%，脚本内部会自动换算成 -0.008。
- 其余 7 支持仓从 SQLite price_data 表读取相邻交易日 close 计算 return。
- 前十大以外的未知剩余仓位，暂按这 7 支可下载股票当日 return 的简单平均值估算。
"""

import argparse
from dataclasses import dataclass

from database.db_utils import get_connection


FUND_NAME = "TDB3098"

# TD 页面当前 Top Ten Holdings。权重单位为基金资产百分比。
KNOWN_HOLDINGS = [
    ("NVIDIA Corporation", "us_nvda", 17.4),
    ("Taiwan Semiconductor Manufacturing Company Limited", "us_tsm", 6.2),
    ("Advanced Micro Devices Inc.", "us_amd", 6.1),
    ("Broadcom Inc.", "us_avgo", 5.9),
    ("Samsung Electronics Company Limited", None, 5.3),
    ("Apple Inc.", "us_aapl", 4.7),
    ("Intel Corporation", "us_intc", 4.2),
    ("SK Hynix Inc.", None, 4.0),
    ("ASML Holding NV", "us_asml", 3.4),
    ("Anthropic PBC private placement", None, 2.4),
]

SAMSUNG_WEIGHT = 5.3
SK_HYNIX_WEIGHT = 4.0
ANTHROPIC_WEIGHT = 2.4
UNKNOWN_WEIGHT = 100.0 - sum(weight for _, _, weight in KNOWN_HOLDINGS)

MARKET_PRICE_HOLDINGS = [
    (name, symbol, weight)
    for name, symbol, weight in KNOWN_HOLDINGS
    if symbol is not None
]


@dataclass
class HoldingReturn:
    name: str
    symbol: str
    weight: float
    previous_date: str
    date: str
    previous_close: float
    close: float
    daily_return: float
    source: str

    @property
    def contribution(self):
        return self.weight / 100.0 * self.daily_return


def parse_return(value):
    """把手动输入的百分比数值转成小数 return。"""

    return float(value) / 100.0


def load_latest_two_prices(symbol, target_date):
    """读取 target_date 及以前最近两条收盘价。"""

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, close
            FROM price_data
            WHERE symbol = ?
              AND date <= ?
              AND close IS NOT NULL
            ORDER BY date DESC
            LIMIT 2
            """,
            (symbol, target_date),
        )
        rows = cursor.fetchall()
    finally:
        conn.close()

    if len(rows) < 2:
        raise RuntimeError(
            f"{symbol} 在 {target_date} 及以前少于两条价格记录，无法计算单日涨跌幅"
        )

    current, previous = rows[0], rows[1]

    return previous, current


def calculate_market_holding_returns(target_date):
    """计算数据库中 7 支可下载持仓的单日 return。"""

    results = []
    for name, symbol, weight in MARKET_PRICE_HOLDINGS:
        previous, current = load_latest_two_prices(symbol, target_date)
        previous_date, previous_close_raw = previous
        current_date, close_raw = current
        previous_close = float(previous_close_raw)
        close = float(close_raw)
        daily_return = close / previous_close - 1

        results.append(
            HoldingReturn(
                name=name,
                symbol=symbol,
                weight=weight,
                previous_date=str(previous_date),
                date=str(current_date),
                previous_close=previous_close,
                close=close,
                daily_return=daily_return,
                source="price_data",
            )
        )

    return results


def estimate_tdb3098_return(target_date, samsung_return, sk_hynix_return):
    """按持仓权重估算基金单日 return。"""

    market_returns = calculate_market_holding_returns(target_date)
    average_market_return = sum(item.daily_return for item in market_returns) / len(
        market_returns
    )

    manual_returns = [
        HoldingReturn(
            name="Samsung Electronics Company Limited",
            symbol="manual_samsung",
            weight=SAMSUNG_WEIGHT,
            previous_date="manual",
            date=target_date,
            previous_close=0,
            close=0,
            daily_return=samsung_return,
            source="manual",
        ),
        HoldingReturn(
            name="SK Hynix Inc.",
            symbol="manual_sk_hynix",
            weight=SK_HYNIX_WEIGHT,
            previous_date="manual",
            date=target_date,
            previous_close=0,
            close=0,
            daily_return=sk_hynix_return,
            source="manual",
        ),
        HoldingReturn(
            name="Anthropic PBC private placement",
            symbol="estimate_anthropic",
            weight=ANTHROPIC_WEIGHT,
            previous_date="estimate",
            date=target_date,
            previous_close=0,
            close=0,
            daily_return=average_market_return,
            source="estimated_from_7_stock_average",
        ),
        HoldingReturn(
            name="Unknown remaining holdings",
            symbol="estimate_unknown",
            weight=UNKNOWN_WEIGHT,
            previous_date="estimate",
            date=target_date,
            previous_close=0,
            close=0,
            daily_return=average_market_return,
            source="estimated_from_7_stock_average",
        ),
    ]

    all_returns = market_returns + manual_returns
    fund_return = sum(item.contribution for item in all_returns)

    return fund_return, average_market_return, all_returns


def format_percent(value):
    return f"{value * 100:.2f}%"


def print_report(target_date, fund_return, average_market_return, returns):
    print(f"{FUND_NAME} estimated daily return for {target_date}: {format_percent(fund_return)}")
    print(f"7-stock average return used for unknown/Anthropic: {format_percent(average_market_return)}")
    print()
    print(
        "name | symbol | weight | return | contribution | source | price dates"
    )
    print("-" * 110)

    for item in sorted(returns, key=lambda row: row.weight, reverse=True):
        print(
            " | ".join(
                [
                    item.name,
                    item.symbol,
                    f"{item.weight:.1f}%",
                    format_percent(item.daily_return),
                    format_percent(item.contribution),
                    item.source,
                    f"{item.previous_date}->{item.date}",
                ]
            )
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="估算 TDB3098 单日涨跌幅，韩国两只持仓使用手动输入 return。"
    )
    parser.add_argument(
        "--date",
        required=True,
        help="目标日期，脚本会读取该日期及以前最近两条 price_data 记录，例如 2026-06-24",
    )
    parser.add_argument(
        "--samsung-return",
        required=True,
        type=parse_return,
        help="Samsung Electronics 当日涨跌幅百分比；1.2 表示上涨 1.2%，-0.8 表示下跌 0.8%",
    )
    parser.add_argument(
        "--sk-hynix-return",
        required=True,
        type=parse_return,
        help="SK Hynix 当日涨跌幅百分比；1.2 表示上涨 1.2%，-0.8 表示下跌 0.8%",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    fund_return, average_market_return, returns = estimate_tdb3098_return(
        target_date=args.date,
        samsung_return=args.samsung_return,
        sk_hynix_return=args.sk_hynix_return,
    )
    print_report(args.date, fund_return, average_market_return, returns)


if __name__ == "__main__":
    main()
