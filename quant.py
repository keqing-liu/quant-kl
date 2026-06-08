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


def run_daily_update(_args):
    """Run the existing main workflow without changing main.py behavior."""

    # runpy.run_module(..., run_name="__main__") 的效果接近在终端执行：
    # python -m main
    # 这样可以复用 main.py 现有流程，而不用复制里面的更新逻辑。
    runpy.run_module("main", run_name="__main__")


def run_etf_summary(args):
    """Show both China ETF and US ETF summaries."""

    # 这里放在函数内部 import，是为了让 `python -m quant --help` 更快更干净：
    # 只是看帮助时，不需要提前加载 pandas / 数据库相关模块。
    from analysis.summary import run_summary

    print("中国 ETF 摘要")
    print("=" * 120)
    run_summary(group="cn-etf", days=args.days)

    print("\n美国 ETF 摘要")
    print("=" * 120)
    run_summary(group="us-etf", days=args.days)


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
    """Run the existing short-term technical score check."""

    from analysis.scoring2 import run_signal_check

    run_signal_check()


def run_trend(_args):
    """Run the existing trend / volatility score example."""

    from analysis.scoring_benchmark import run_signal_check

    run_signal_check(["sh510310"])


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
        help="输出中国 ETF 和美国 ETF 摘要",
    )
    add_days_argument(summary_parser)
    summary_parser.set_defaults(func=run_etf_summary)

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
