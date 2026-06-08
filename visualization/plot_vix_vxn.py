"""绘制最近两个月 Cboe 风险指标走势。"""

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

import matplotlib.pyplot as plt
import pandas as pd

from database.db_utils import get_connection


VIX_SYMBOL = "cboe_vix"
VXN_SYMBOL = "cboe_vxn"
VVIX_SYMBOL = "cboe_vvix"
SKEW_SYMBOL = "cboe_skew"
MARKET_INDICATOR_SYMBOLS = [
    VIX_SYMBOL,
    VXN_SYMBOL,
    VVIX_SYMBOL,
    SKEW_SYMBOL,
]
SYMBOL_NAMES = {
    VIX_SYMBOL: "VIX",
    VXN_SYMBOL: "VXN",
    VVIX_SYMBOL: "VVIX",
    SKEW_SYMBOL: "SKEW",
}


def load_market_indicator_data(months=2):
    """从 price_data 读取最近 months 个月的 Cboe 风险指标收盘价。"""

    conn = get_connection()

    try:
        placeholders = ",".join("?" for _ in MARKET_INDICATOR_SYMBOLS)
        latest_date = pd.read_sql(
            f"""
            SELECT MAX(date) AS latest_date
            FROM price_data
            WHERE symbol IN ({placeholders})
            """,
            conn,
            params=MARKET_INDICATOR_SYMBOLS,
        )["latest_date"].iloc[0]

        if latest_date is None:
            return pd.DataFrame()

        start_date = (
            pd.to_datetime(latest_date) - pd.DateOffset(months=months)
        ).strftime("%Y-%m-%d")

        df = pd.read_sql(
            f"""
            SELECT symbol, date, close
            FROM price_data
            WHERE symbol IN ({placeholders})
              AND date >= ?
            ORDER BY date
            """,
            conn,
            params=MARKET_INDICATOR_SYMBOLS + [start_date],
        )
    finally:
        conn.close()

    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])

    wide_df = df.pivot(index="date", columns="symbol", values="close")
    wide_df = wide_df.rename(columns=SYMBOL_NAMES)
    wide_df["VXN-VIX"] = wide_df["VXN"] - wide_df["VIX"]

    return wide_df


def plot_vix_vxn(months=2, output_path=None):
    """绘制 VIX / VXN、SKEW、VVIX 与 VXN-VIX 差值走势图。"""

    print(f"开始绘制最近 {months} 个月 Cboe 风险指标走势图...")

    df = load_market_indicator_data(months=months)

    if df.empty:
        print("没有读取到 Cboe 风险指标数据")
        return

    x = df.index.to_numpy()

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(16, 10),
        constrained_layout=True,
    )
    ax1, ax2, ax3, ax4 = axes.ravel()

    ax1.plot(x, df["VIX"].to_numpy(), label="VIX", linewidth=1.8)
    ax1.plot(x, df["VXN"].to_numpy(), label="VXN", linewidth=1.8)
    ax1.set_title(f"VIX & VXN - Recent {months} Months")
    ax1.set_ylabel("Index Level")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(
        x,
        df["SKEW"].to_numpy(),
        label="SKEW",
        color="tab:green",
        linewidth=1.8,
    )
    ax2.set_title("SKEW Index")
    ax2.set_ylabel("Index Level")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    ax3.plot(
        x,
        df["VVIX"].to_numpy(),
        label="VVIX",
        color="tab:red",
        linewidth=1.8,
    )
    ax3.set_title("VVIX Index")
    ax3.set_ylabel("Index Level")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    ax4.plot(
        x,
        df["VXN-VIX"].to_numpy(),
        label="VXN-VIX",
        color="tab:purple",
        linewidth=1.8,
    )
    ax4.axhline(0, color="black", linestyle="--", linewidth=1)
    ax4.set_title("VXN - VIX Spread")
    ax4.set_xlabel("Date")
    ax4.set_ylabel("Spread")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    for ax in axes.ravel():
        ax.tick_params(axis="x", rotation=30)

    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"图像已保存到: {output_file}")
    else:
        plt.show()

    print("Cboe 风险指标走势图绘制完成")


def plot_cboe_risk_indicators(months=2, output_path=None):
    """plot_vix_vxn 的语义化别名。"""

    plot_vix_vxn(months=months, output_path=output_path)


def parse_args():
    parser = argparse.ArgumentParser(
        description="绘制最近两个月 VIX、VXN、SKEW、VVIX 以及 VXN-VIX 差值走势。"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=2,
        help="回看月份数，默认 2。",
    )
    parser.add_argument(
        "--output",
        help="可选：保存图片路径，例如 output/cboe_risk_indicators_recent_2m.png。",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    plot_vix_vxn(months=args.months, output_path=args.output)
