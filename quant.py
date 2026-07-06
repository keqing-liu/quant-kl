"""Convenience CLI for daily ETF research workflows.

This module keeps the original scripts intact and adds a shorter command layer:

    python -m quant e summary
    python -m quant e risk

你可以把这个文件理解成一个“命令路由器”：
终端输入的短命令会先进入这里，再由这里调用项目里已经存在的脚本函数。
"""

import argparse
import runpy


# 默认展示最近 5 个交易日；所有带 --days 的命令都会使用这个默认值。
DEFAULT_DAYS = 5
DEFAULT_FINANCIAL_DATASETS = ("indicators", "statements")
FINANCIAL_DATASET_CHOICES = set(DEFAULT_FINANCIAL_DATASETS)


def run_daily_update(_args):
    """Run the existing main workflow without changing main.py behavior."""

    # runpy.run_module(..., run_name="__main__") 的效果接近在终端执行：
    # python -m main
    # 这样可以复用 main.py 现有流程，而不用复制里面的更新逻辑。
    runpy.run_module("main", run_name="__main__")


def run_etf_summary(args):
    """Show China/US ETF, stock, and US index summaries."""

    # 这里放在函数内部 import，是为了让 `python -m quant --help` 更快更干净：
    # 只是看帮助时，不需要提前加载 pandas / 数据库相关模块。
    from analysis.summary import run_summary

    print("中国 ETF 摘要")
    print("=" * 120)
    run_summary(group="cn-etf", days=args.days)

    print("\n中国个股摘要")
    print("=" * 120)
    run_summary(group="cn-stock", days=args.days)

    print("\n加拿大个股摘要")
    print("=" * 120)
    run_summary(group="ca-stock", days=args.days)

    print("\n美国 ETF 摘要")
    print("=" * 120)
    run_summary(group="us-etf", days=args.days)

    print("\n美国个股摘要")
    print("=" * 120)
    run_summary(group="us-stock", days=args.days)

    print("\n美国指数摘要")
    print("=" * 120)
    run_summary(group="us-index", days=args.days)


def run_etf_weekly_summary(args):
    """Show China/US ETF, stock, and US index weekly summaries."""

    from analysis.summary import run_summary

    print("中国 ETF 周线摘要")
    print("=" * 120)
    run_summary(group="cn-etf", days=args.days, frequency="weekly")

    print("\n中国个股周线摘要")
    print("=" * 120)
    run_summary(group="cn-stock", days=args.days, frequency="weekly")

    print("\n美国 ETF 周线摘要")
    print("=" * 120)
    run_summary(group="us-etf", days=args.days, frequency="weekly")

    print("\n美国个股周线摘要")
    print("=" * 120)
    run_summary(group="us-stock", days=args.days, frequency="weekly")

    print("\n美国指数周线摘要")
    print("=" * 120)
    run_summary(group="us-index", days=args.days, frequency="weekly")


def run_group_summary(group):
    """Build a handler for one summary group."""

    # argparse 的 set_defaults(func=...) 需要绑定一个“接收 args 的函数”。
    # cn/us/risk 三个命令只有 group 不同，所以这里用闭包生成小函数，
    # 避免重复写三段几乎一样的 run_summary 调用。
    def handler(args):
        from analysis.summary import run_summary

        run_summary(group=group, days=args.days)

    return handler


def run_score(_args):
    """Run the short-term oversold score check."""

    from analysis.short_term_oversold_score import run_signal_check

    run_signal_check()


def run_trend(_args):
    """Run the ETF trend / volatility score example."""

    from analysis.etf_trend_volatility_score import run_signal_check

    run_signal_check(["sh510310"])


def run_weekly_indicators(_args):
    """Aggregate daily prices to weekly bars and calculate weekly indicators."""

    from analysis.indicators import run_indicator_analysis

    run_indicator_analysis(frequency="weekly")


def run_backfill(args):
    """Backfill one US stock/ETF/index symbol."""

    from data_manager.data_manager import DataManager
    from database.db_utils import initialize_database

    initialize_database()

    manager = DataManager()
    # CLI 只负责收集参数；真正决定下载源和日期窗口的是 DataManager。
    manager.backfill_stooq_symbol(
        args.symbol,
        max_pages=args.max_pages,
        start_date=args.start_date,
        end_date=args.end_date,
    )


def run_financial_download(args):
    """Download one A-share company's financial data into SQLite."""

    # 延迟导入，避免查看 quant 帮助时提前加载数据库和财务下载模块。
    from data_fetch.update_financial_data import update_financial_indicators

    update_financial_indicators(
        symbols=[args.symbol],
        start_year=args.start_year,
        sleep_seconds=args.sleep,
        retries=args.retries,
        force_refresh=args.force_refresh,
        datasets=args.datasets,
    )


def run_daily_report(args):
    """Generate a Markdown daily research report from local SQLite data."""

    from analysis.daily_report import write_daily_report

    output_path = write_daily_report(
        report_date=args.date,
        output_dir=args.output_dir,
        days=args.days,
    )

    print(f"日报已生成: {output_path}")


def parse_financial_datasets(value):
    """Parse and validate a comma-separated financial dataset list."""

    datasets = tuple(item.strip() for item in value.split(",") if item.strip())
    invalid = [item for item in datasets if item not in FINANCIAL_DATASET_CHOICES]

    if not datasets:
        raise argparse.ArgumentTypeError("至少选择一个财务数据集")

    if invalid:
        valid = ", ".join(DEFAULT_FINANCIAL_DATASETS)
        raise argparse.ArgumentTypeError(
            f"未知财务数据集 {invalid[0]}; 可选值: {valid}"
        )

    return datasets


def add_days_argument(parser):
    """给某个子命令添加通用的 --days 参数。"""

    # 多个命令都需要 --days，把它抽成函数后，默认值和帮助文案只维护一处。
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"输出最近几个交易日；默认 {DEFAULT_DAYS}",
    )


def build_parser():
    """创建并配置整个命令行解析器。"""

    # ArgumentParser 负责把终端文字解析成 Python 对象。
    # 例如 `python -m quant e cn --days 3` 会解析出：
    # args.command == "e"
    # args.etf_command == "cn"
    # args.days == 3
    parser = argparse.ArgumentParser(
        prog="python -m quant",
        description="量化研究短命令入口",
    )

    # 第一层子命令。目前只有 e/etf，以后如果要加基本面，可以再加 f/fundamental。
    subparsers = parser.add_subparsers(dest="command")

    etf_parser = subparsers.add_parser(
        "e",
        aliases=["etf"],
        help="ETF 日常研究命令",
    )

    # 第二层子命令，也就是 `python -m quant e summary` 里的 summary/cn/us/risk。
    etf_subparsers = etf_parser.add_subparsers(dest="etf_command")

    update_parser = etf_subparsers.add_parser(
        "update",
        help="运行 main.py，更新行情并计算技术指标",
    )
    # set_defaults(func=...) 是这个 CLI 的核心：
    # parse_args() 解析到具体命令后，会把对应函数挂到 args.func 上。
    update_parser.set_defaults(func=run_daily_update)

    summary_parser = etf_subparsers.add_parser(
        "summary",
        help="输出中美 ETF、个股和美国指数摘要",
    )
    add_days_argument(summary_parser)
    summary_parser.set_defaults(func=run_etf_summary)

    weekly_summary_parser = etf_subparsers.add_parser(
        "weekly-summary",
        help="输出中美 ETF、个股和美国指数周线摘要",
    )
    add_days_argument(weekly_summary_parser)
    weekly_summary_parser.set_defaults(func=run_etf_weekly_summary)

    cn_parser = etf_subparsers.add_parser(
        "cn",
        help="只输出中国 ETF 摘要",
    )
    add_days_argument(cn_parser)
    cn_parser.set_defaults(func=run_group_summary("cn-etf"))

    us_parser = etf_subparsers.add_parser(
        "us",
        help="只输出美国 ETF 摘要",
    )
    add_days_argument(us_parser)
    us_parser.set_defaults(func=run_group_summary("us-etf"))

    risk_parser = etf_subparsers.add_parser(
        "risk",
        help="输出美国风险观察组合摘要",
    )
    add_days_argument(risk_parser)
    risk_parser.set_defaults(func=run_group_summary("us-risk"))

    score_parser = etf_subparsers.add_parser(
        "score",
        help="运行短期技术指标打分",
    )
    score_parser.set_defaults(func=run_score)

    trend_parser = etf_subparsers.add_parser(
        "trend",
        help="运行趋势 / 波动率打分示例",
    )
    trend_parser.set_defaults(func=run_trend)

    weekly_parser = etf_subparsers.add_parser(
        "weekly",
        help="由日线聚合周线行情，并计算周线技术指标",
    )
    weekly_parser.set_defaults(func=run_weekly_indicators)

    backfill_parser = etf_subparsers.add_parser(
        "backfill",
        help="只补一个美国股票/ETF/指数的历史行情",
    )
    backfill_parser.add_argument(
        "symbol",
        help="美国标的，例如 NDQ、^ndq、QQQ、AAPL、SPY、BRK-B",
    )
    backfill_parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="旧版 Stooq 分页兼容参数；当前 FMP/Twelve Data 下载不使用",
    )
    backfill_parser.add_argument(
        "--start-date",
        default=None,
        # 日期参数会一路传给 FMP/Twelve Data，用来只补一个小区间。
        help="FMP/Twelve Data 下载起始日期，例如 2026-06-13；默认最近约 5 年",
    )
    backfill_parser.add_argument(
        "--end-date",
        default=None,
        help="FMP/Twelve Data 下载结束日期，例如 2026-06-16；默认今天",
    )
    backfill_parser.set_defaults(func=run_backfill)

    fundamental_parser = subparsers.add_parser(
        "f",
        aliases=["fundamental"],
        help="A 股基本面数据命令",
    )
    fundamental_subparsers = fundamental_parser.add_subparsers(
        dest="fundamental_command"
    )

    financial_download_parser = fundamental_subparsers.add_parser(
        "download",
        help="下载一只 A 股从指定年份开始的财务数据并写入 SQLite",
    )
    financial_download_parser.add_argument(
        "symbol",
        help="A 股代码，例如 sh600519、sz000001 或 600519",
    )
    financial_download_parser.add_argument(
        "--start-year",
        type=int,
        required=True,
        help="下载和保留数据的起始会计年度，例如 2022",
    )
    financial_download_parser.add_argument(
        "--datasets",
        type=parse_financial_datasets,
        default=DEFAULT_FINANCIAL_DATASETS,
        help="数据集，逗号分隔；可选 indicators,statements；默认全部",
    )
    financial_download_parser.add_argument(
        "--sleep",
        type=float,
        default=8,
        help="失败重试前等待秒数；默认 8 秒",
    )
    financial_download_parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="下载失败后的重试次数；默认 2 次",
    )
    financial_download_parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="本地已是最新时也重新写入接口返回的已有记录",
    )
    financial_download_parser.set_defaults(func=run_financial_download)

    report_parser = subparsers.add_parser(
        "report",
        help="研究报告生成命令",
    )
    report_subparsers = report_parser.add_subparsers(dest="report_command")

    daily_report_parser = report_subparsers.add_parser(
        "daily",
        help="生成每日交易研究 Markdown 日报",
    )
    daily_report_parser.add_argument(
        "--date",
        default=None,
        help="日报日期，默认今天，例如 2026-06-23",
    )
    daily_report_parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"摘要读取最近几个交易日/周线；默认 {DEFAULT_DAYS}",
    )
    daily_report_parser.add_argument(
        "--output-dir",
        default=None,
        help="日报输出目录；默认 reports/daily",
    )
    daily_report_parser.set_defaults(func=run_daily_report)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # 如果用户只输入 `python -m quant` 或 `python -m quant e`，
    # argparse 不会知道要执行哪个具体任务，所以这里打印帮助信息。
    if not hasattr(args, "func"):
        parser.print_help()
        return

    # 真正执行命令。比如 e cn 会执行 run_group_summary("cn-etf") 生成的 handler。
    args.func(args)


if __name__ == "__main__":
    main()
