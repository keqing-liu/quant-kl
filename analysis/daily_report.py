"""生成每日交易研究 Markdown 日报。

日报只读取本地 SQLite，不下载新行情，也不生成真实交易指令。
"""

import argparse
import re
from datetime import date
from pathlib import Path

import pandas as pd

from analysis.etf_trend_volatility_score import check_signal as check_trend_signal
from analysis.short_term_oversold_score import (
    check_signal as check_oversold_signal,
    get_all_symbols as get_indicator_symbols,
)
from analysis.summary import (
    build_group_symbols,
    get_market_indicator_symbols,
    load_price_summary_data,
    load_summary_data,
)
from data_fetch.fetch_cboe_market import build_cboe_index_internal_symbol
from data_fetch.fetch_us_market import build_us_index_symbol, build_us_symbol
from database.db_utils import get_connection, initialize_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports" / "daily"


SUMMARY_GROUPS = [
    ("中国 ETF 摘要", "cn-etf"),
    ("美国 ETF 摘要", "us-etf"),
    ("美国个股摘要", "us-stock"),
]

WEEKLY_GROUPS = [
    ("中国 ETF 周线趋势", "cn-etf"),
    ("美国 ETF 周线趋势", "us-etf"),
    ("美国指数周线趋势", "us-index"),
]


def _clean_watchlist_comment(comment):
    """把 watchlist 行尾注释整理成适合日报展示的资产名称。"""

    name = comment.strip()
    for separator in ("；", ";"):
        if separator in name:
            name = name.split(separator, 1)[0].strip()

    return name


def _load_watchlist_name_map():
    """从 config/watchlist.py 的行尾注释读取 symbol -> 名称映射。"""

    watchlist_path = PROJECT_ROOT / "config" / "watchlist.py"
    text = watchlist_path.read_text(encoding="utf-8")
    name_map = {}
    current_group = None

    group_pattern = re.compile(r'"([^"]+)"\s*:\s*\[')
    item_pattern = re.compile(r'["\']([^"\']+)["\']\s*,?\s*(?:#\s*(.*))?$')

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        group_match = group_pattern.match(stripped)
        if group_match:
            current_group = group_match.group(1)
            continue

        if current_group and stripped.startswith("]"):
            current_group = None
            continue

        if not current_group:
            continue

        item_match = item_pattern.match(stripped)
        if not item_match:
            continue

        raw_symbol = item_match.group(1)
        raw_comment = item_match.group(2)
        if not raw_comment:
            continue

        name = _clean_watchlist_comment(raw_comment)
        if not name:
            continue

        name_map[raw_symbol] = name

        if current_group in {"ETF", "STOCK"}:
            name_map[raw_symbol] = name
        elif current_group in {"US_ETF", "US_STOCK"}:
            name_map[build_us_symbol(raw_symbol)] = name
        elif current_group == "US_INDEX":
            name_map[build_us_index_symbol(raw_symbol)] = name
        elif current_group == "US_MARKET_INDICATOR":
            name_map[build_cboe_index_internal_symbol(raw_symbol)] = name

    return name_map


def _asset_name(symbol, name_map=None):
    name_map = name_map or _load_watchlist_name_map()
    return name_map.get(symbol, "")


def _add_asset_names(df, symbol_column="symbol", name_column="名称", name_map=None):
    if df is None or df.empty or symbol_column not in df.columns:
        return df

    result = df.copy()
    name_map = name_map or _load_watchlist_name_map()
    result[name_column] = result[symbol_column].map(
        lambda symbol: _asset_name(symbol, name_map=name_map)
    )

    columns = [name_column] + [
        column for column in result.columns if column != name_column
    ]

    return result[columns]


def _read_sql(sql, params=None):
    conn = get_connection()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


def _format_value(value):
    if pd.isna(value):
        return ""

    if isinstance(value, float):
        return f"{value:.2f}"

    return str(value)


def _markdown_table(df, columns=None, max_rows=None):
    if df is None or df.empty:
        return "暂无数据"

    table_df = df.copy()
    if columns is not None:
        for column in columns:
            if column not in table_df.columns:
                table_df[column] = None
        table_df = table_df[columns]

    if max_rows is not None:
        table_df = table_df.head(max_rows)

    table_df = table_df.rename(columns=lambda col: str(col))

    header = "| " + " | ".join(table_df.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(table_df.columns)) + " |"

    rows = []
    for _, row in table_df.iterrows():
        rows.append(
            "| "
            + " | ".join(_format_value(row[col]) for col in table_df.columns)
            + " |"
        )

    return "\n".join([header, separator] + rows)


def _latest_price_status():
    return _read_sql(
        """
        SELECT
            symbol,
            COUNT(*) AS rows_count,
            MIN(date) AS first_date,
            MAX(date) AS latest_date
        FROM price_data
        GROUP BY symbol
        ORDER BY latest_date DESC, symbol
        """
    )


def _latest_update_logs():
    return _read_sql(
        """
        SELECT
            l.symbol,
            l.asset_type,
            l.update_time,
            l.start_date,
            l.end_date,
            l.rows_downloaded,
            l.rows_inserted,
            l.status,
            l.message,
            l.data_source
        FROM data_update_log AS l
        JOIN (
            SELECT symbol, MAX(id) AS latest_id
            FROM data_update_log
            GROUP BY symbol
        ) AS latest
        ON l.symbol = latest.symbol
        AND l.id = latest.latest_id
        ORDER BY l.update_time DESC, l.symbol
        """
    )


def _build_group_summary(group, days=5, frequency="daily"):
    symbols = build_group_symbols(group)
    market_indicator_symbols = get_market_indicator_symbols()
    name_map = _load_watchlist_name_map()
    rows = []

    for symbol in symbols:
        if symbol in market_indicator_symbols:
            df = _load_market_indicator_summary(symbol, frequency=frequency)
            if df.empty:
                rows.append({
                    "名称": _asset_name(symbol, name_map=name_map),
                    "symbol": symbol,
                    "status": "无价格数据",
                })
                continue

            latest = df.iloc[0]
            rows.append(
                {
                    "名称": _asset_name(symbol, name_map=name_map),
                    "symbol": symbol,
                    "date": latest["date"],
                    "close": latest["close"],
                    "MA20": latest.get("MA20"),
                    "MA60": latest.get("MA60"),
                    "status": "价格序列",
                }
            )
            continue

        df = load_summary_data(symbol, days=days, frequency=frequency)
        if df.empty:
            rows.append({
                "名称": _asset_name(symbol, name_map=name_map),
                "symbol": symbol,
                "status": "无指标数据",
            })
            continue

        latest = df.iloc[0]
        rows.append(
            {
                "名称": _asset_name(symbol, name_map=name_map),
                "symbol": symbol,
                "date": latest["date"],
                "close": latest["close"],
                "MA20": latest.get("MA20"),
                "MA60": latest.get("MA60"),
                "BOLL_UPPER": latest.get("BOLL_UPPER"),
                "BOLL_LOWER": latest.get("BOLL_LOWER"),
                "K": latest.get("K"),
                "J": latest.get("J"),
                "CCI": latest.get("CCI"),
                "status": _describe_technical_state(latest),
            }
        )

    return pd.DataFrame(rows)


def _load_market_indicator_summary(symbol, frequency="daily"):
    """读取 Cboe 风险指标最新价格和日线均线。"""

    if frequency != "daily":
        return load_price_summary_data(symbol, days=1, frequency=frequency)

    return _read_sql(
        """
        SELECT
            p.date,
            p.open,
            p.high,
            p.low,
            p.close,
            p.volume,
            i.MA20,
            i.MA60
        FROM price_data AS p
        LEFT JOIN indicators AS i
        ON p.symbol = i.symbol
        AND p.date = i.date
        WHERE p.symbol = ?
        ORDER BY p.date DESC
        LIMIT 1
        """,
        params=(symbol,),
    )


def _describe_technical_state(row):
    notes = []

    if pd.notna(row.get("close")) and pd.notna(row.get("MA20")):
        if row["close"] >= row["MA20"]:
            notes.append("收盘价高于 MA20")
        else:
            notes.append("收盘价低于 MA20")

    if pd.notna(row.get("MA20")) and pd.notna(row.get("MA60")):
        if row["MA20"] >= row["MA60"]:
            notes.append("MA20 高于 MA60，短中期均线偏强")
        else:
            notes.append("MA20 低于 MA60，短中期均线偏弱")

    if pd.notna(row.get("K")) and row["K"] < 20:
        notes.append("KDJ 低位")

    if pd.notna(row.get("CCI")) and row["CCI"] < -120:
        notes.append("CCI 偏冷")

    if not notes:
        notes.append("指标中性或数据不足")

    return "；".join(notes)


def _risk_summary(days=5):
    risk_df = _build_group_summary("us-risk", days=days, frequency="daily")
    if risk_df.empty:
        return risk_df

    def describe(row):
        symbol = row.get("symbol", "")
        close = row.get("close")

        if symbol == "cboe_vix" and pd.notna(close):
            if close >= 30:
                return "波动率显著偏高，注意风险观察"
            if close >= 20:
                return "波动率偏高，保持观察"
            return "波动率相对平稳"

        if symbol == "cboe_vxn" and pd.notna(close):
            if close >= 35:
                return "纳指波动率显著偏高"
            if close >= 25:
                return "纳指波动率偏高"
            return "纳指波动率相对平稳"

        return row.get("status", "")

    risk_df["risk_note"] = risk_df.apply(describe, axis=1)
    return risk_df


def _oversold_scores():
    rows = []
    for symbol in get_indicator_symbols():
        try:
            rows.append(check_oversold_signal(symbol))
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values(["Score", "ETF"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _trend_scores():
    rows = []
    target_symbols = []
    for group in ("cn-etf", "us-etf", "us-index"):
        target_symbols.extend(build_group_symbols(group))

    for symbol in target_symbols:
        try:
            results = check_trend_signal(symbol)
        except Exception:
            continue

        if results:
            rows.append(results[0])

    if not rows:
        return pd.DataFrame()

    return (
        pd.DataFrame(rows)
        .sort_values(["Score", "ETF"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _data_quality_summary():
    checks = [
        (
            "重复交易日",
            """
            SELECT symbol, date, COUNT(*) AS count
            FROM price_data
            GROUP BY symbol, date
            HAVING COUNT(*) > 1
            ORDER BY symbol, date
            """,
        ),
        (
            "close 缺失或小于等于 0",
            """
            SELECT symbol, date, close
            FROM price_data
            WHERE close IS NULL OR close <= 0
            ORDER BY symbol, date
            """,
        ),
        (
            "OHLC 价格逻辑异常",
            """
            SELECT symbol, date, open, high, low, close
            FROM price_data
            WHERE
                high < low
                OR close > high
                OR close < low
                OR open > high
                OR open < low
            ORDER BY symbol, date
            """,
        ),
        (
            "volume 缺失或小于 0",
            """
            SELECT symbol, date, volume
            FROM price_data
            WHERE volume IS NULL OR volume < 0
            ORDER BY symbol, date
            """,
        ),
    ]

    rows = []
    details = {}
    for title, sql in checks:
        df = _read_sql(sql)
        rows.append(
            {
                "检查项": title,
                "问题数": len(df),
                "状态": "通过" if df.empty else "需检查",
            }
        )
        if not df.empty:
            details[title] = df

    return pd.DataFrame(rows), details


def _observation_list(oversold_df, trend_df, risk_df):
    observations = []

    if oversold_df is not None and not oversold_df.empty:
        for _, row in oversold_df[oversold_df["Score"] >= 3].head(5).iterrows():
            observations.append(
                f"- {row['ETF']}：短期超跌评分 {row['Score']}，作为反弹观察对象。"
            )

    if trend_df is not None and not trend_df.empty:
        for _, row in trend_df[trend_df["Score"] >= 2].head(5).iterrows():
            observations.append(
                f"- {row['ETF']}：趋势/波动率评分 {row['Score']}，观察趋势延续性。"
            )

    if risk_df is not None and not risk_df.empty:
        elevated = risk_df[
            risk_df["risk_note"].astype(str).str.contains("偏高|显著", regex=True)
        ]
        for _, row in elevated.head(3).iterrows():
            observations.append(f"- {row['symbol']}：{row['risk_note']}。")

    if not observations:
        observations.append("- 暂无高优先级观察项，按既有 watchlist 继续跟踪。")

    observations.append("- 本日报只用于研究观察，不构成任何投资建议或交易指令。")

    return "\n".join(observations)


def build_daily_report(report_date=None, days=5):
    """返回日报 Markdown 文本。"""

    initialize_database()

    report_date = report_date or date.today().strftime("%Y-%m-%d")

    latest_status = _latest_price_status()
    update_logs = _latest_update_logs()
    risk_df = _risk_summary(days=days)
    oversold_df = _add_asset_names(_oversold_scores(), symbol_column="ETF")
    trend_df = _add_asset_names(_trend_scores(), symbol_column="ETF")
    quality_df, quality_details = _data_quality_summary()

    lines = [
        f"# 每日交易研究日报 - {report_date}",
        "",
        "> 本日报由本地 SQLite 数据生成，只用于研究观察，不构成投资建议。",
        "",
        "## 数据最新日期和更新状态",
        "",
        "### 行情数据区间",
        "",
        _markdown_table(
            _add_asset_names(latest_status),
            columns=["名称", "symbol", "rows_count", "first_date", "latest_date"],
            max_rows=30,
        ),
        "",
        "### 最近一次更新日志",
        "",
        _markdown_table(
            _add_asset_names(update_logs),
            columns=[
                "名称",
                "symbol",
                "asset_type",
                "update_time",
                "start_date",
                "end_date",
                "rows_inserted",
                "status",
                "data_source",
            ],
            max_rows=30,
        ),
        "",
        "## 美国风险指标摘要",
        "",
        _markdown_table(
            risk_df,
            columns=["名称", "symbol", "date", "close", "MA20", "MA60", "risk_note"],
        ),
    ]

    for title, group in SUMMARY_GROUPS:
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                _markdown_table(
                    _build_group_summary(group, days=days),
                    columns=[
                        "名称",
                        "symbol",
                        "date",
                        "close",
                        "MA20",
                        "MA60",
                        "BOLL_UPPER",
                        "BOLL_LOWER",
                        "K",
                        "J",
                        "CCI",
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 短期超跌和趋势信号",
            "",
            "### 短期超跌评分",
            "",
            _markdown_table(
                oversold_df,
                columns=[
                    "名称",
                    "ETF",
                    "Date",
                    "Close",
                    "MA20",
                    "MA60",
                    "BOLL_UPPER",
                    "BOLL_LOWER",
                    "K",
                    "J",
                    "CCI",
                    "Score",
                ],
                max_rows=15,
            ),
            "",
            "### 趋势 / 波动率评分",
            "",
            _markdown_table(
                trend_df,
                columns=[
                    "名称",
                    "ETF",
                    "Date",
                    "Close",
                    "MA50",
                    "VOLATILITY20",
                    "VOLATILITY252",
                    "Score",
                ],
                max_rows=15,
            ),
            "",
            "## 周线趋势摘要",
        ]
    )

    for title, group in WEEKLY_GROUPS:
        lines.extend(
            [
                "",
                f"### {title}",
                "",
                _markdown_table(
                    _build_group_summary(group, days=days, frequency="weekly"),
                    columns=[
                        "名称",
                        "symbol",
                        "date",
                        "close",
                        "MA20",
                        "MA60",
                        "BOLL_UPPER",
                        "BOLL_LOWER",
                        "K",
                        "J",
                        "CCI",
                    ],
                ),
            ]
        )

    lines.extend(
        [
            "",
            "## 数据质量提醒",
            "",
            _markdown_table(quality_df),
        ]
    )

    for title, detail_df in quality_details.items():
        lines.extend(
            [
                "",
                f"### {title}明细",
                "",
                _markdown_table(_add_asset_names(detail_df), max_rows=20),
            ]
        )

    lines.extend(
        [
            "",
            "## 明日观察清单",
            "",
            _observation_list(oversold_df, trend_df, risk_df),
            "",
        ]
    )

    return "\n".join(lines)


def write_daily_report(report_date=None, output_dir=None, days=5):
    """生成日报并写入 Markdown 文件，返回输出路径。"""

    report_date = report_date or date.today().strftime("%Y-%m-%d")
    output_dir = Path(output_dir) if output_dir else DEFAULT_REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    report_text = build_daily_report(report_date=report_date, days=days)
    output_path = output_dir / f"{report_date}.md"
    output_path.write_text(report_text, encoding="utf-8")

    return output_path


def parse_args():
    parser = argparse.ArgumentParser(description="生成每日交易研究 Markdown 日报")
    parser.add_argument(
        "--date",
        default=None,
        help="日报日期，默认今天，例如 2026-06-23",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="摘要读取最近几个交易日/周线；默认 5",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="日报输出目录；默认 reports/daily",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    path = write_daily_report(
        report_date=args.date,
        output_dir=args.output_dir,
        days=args.days,
    )
    print(f"日报已生成: {path}")
