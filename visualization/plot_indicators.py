"""从 SQLite 数据库读取 ETF / 股票技术指标，并绘制技术指标图。

matplotlib 的核心思想是：
1. 创建 figure（画布）
2. 创建 subplot（子图）
3. 在不同 axes 上 plot 不同曲线

这里我们会：
- 从 SQLite 的 indicators 表读取指标
- 从 price_data 表读取 close 价格
- 绘制：
    1. 价格 + 均线 + 布林带
    2. KDJ
    3. CCI
"""

import pandas as pd
import matplotlib.pyplot as plt

from database.db_utils import get_connection


# =========================
# 从 SQLite 读取指标数据
# =========================

def load_indicator_data(symbol):

    # 获取数据库连接。
    conn = get_connection()

    # 从 indicators 表读取技术指标。
    # 同时 JOIN price_data 表读取 close 收盘价。
    #
    # JOIN 条件：
    # symbol 和 date 必须同时一致。
    #
    # ORDER BY date：
    # 保证时间顺序从旧到新。
    df = pd.read_sql("""

        SELECT

            i.symbol,
            i.date,

            p.close,

            i.MA20,
            i.MA60,

            i.BOLL_UPPER,
            i.BOLL_LOWER,

            i.K,
            i.D,
            i.J,

            i.CCI

        FROM indicators AS i

        JOIN price_data AS p

        ON i.symbol = p.symbol
        AND i.date = p.date

        WHERE i.symbol = ?

        ORDER BY i.date

    """, conn, params=(symbol,))

    conn.close()

    return df


# =========================
# 绘制技术指标图
# =========================

def plot_indicators(symbol):

    print(f"开始绘制 {symbol} 技术指标图...")

    # 从数据库读取指标数据。
    df = load_indicator_data(symbol)

    # 如果没有数据，直接退出。
    if df.empty:

        print(f"{symbol} 没有指标数据")

        return

    # SQLite 中 date 通常是字符串；
    # 转 datetime 后 matplotlib 才能正确显示时间轴。
    df["date"] = pd.to_datetime(df["date"])

    # =========================
    # matplotlib / pandas 兼容处理
    # =========================

    # 新版 pandas 的 Series 不再支持某些 matplotlib 内部操作。
    #
    # 所以：
    # 把 pandas Series 转成 numpy array，
    # 能避免：
    #
    # ValueError:
    # Multi-dimensional indexing is no longer supported
    #
    # x 作为横轴时间序列。
    x = df["date"].to_numpy()

    # =========================
    # 创建画布
    # =========================

    # figsize 单位是英寸。
    # 这里创建一个较大的画布。
    fig = plt.figure(figsize=(16, 12))

    # =========================
    # 子图1：
    # 价格 + 均线 + 布林带
    # =========================

    # 3 行 1 列中的第 1 个子图。
    ax1 = plt.subplot(3, 1, 1)

    # 收盘价。
    ax1.plot(
        x,
        df["close"].to_numpy(),
        label="Close"
    )

    # 20 日均线。
    ax1.plot(
        x,
        df["MA20"].to_numpy(),
        label="MA20"
    )

    # 60 日均线。
    ax1.plot(
        x,
        df["MA60"].to_numpy(),
        label="MA60"
    )

    # 布林上轨。
    ax1.plot(
        x,
        df["BOLL_UPPER"].to_numpy(),
        linestyle="--",
        label="BOLL Upper"
    )

    # 布林下轨。
    ax1.plot(
        x,
        df["BOLL_LOWER"].to_numpy(),
        linestyle="--",
        label="BOLL Lower"
    )

    # 图标题。
    ax1.set_title(
        f"{symbol} Price & Bollinger Bands"
    )

    # 显示图例。
    ax1.legend()

    # 打开网格。
    ax1.grid(True)

    # =========================
    # 子图2：KDJ
    # =========================

    ax2 = plt.subplot(3, 1, 2)

    # K线。
    ax2.plot(
        x,
        df["K"].to_numpy(),
        label="K"
    )

    # D线。
    ax2.plot(
        x,
        df["D"].to_numpy(),
        label="D"
    )

    # J线。
    ax2.plot(
        x,
        df["J"].to_numpy(),
        label="J"
    )

    # KDJ 常见超买参考线。
    ax2.axhline(
        80,
        linestyle="--"
    )

    # KDJ 常见超卖参考线。
    ax2.axhline(
        20,
        linestyle="--"
    )

    ax2.set_title("KDJ")

    ax2.legend()

    ax2.grid(True)

    # =========================
    # 子图3：CCI
    # =========================

    ax3 = plt.subplot(3, 1, 3)

    # CCI 曲线。
    ax3.plot(
        x,
        df["CCI"].to_numpy(),
        label="CCI"
    )

    # +100 常作为强势参考线。
    ax3.axhline(
        100,
        linestyle="--"
    )

    # -100 常作为弱势参考线。
    ax3.axhline(
        -100,
        linestyle="--"
    )

    ax3.set_title("CCI")

    ax3.legend()

    ax3.grid(True)

    # =========================
    # 自动调整布局
    # =========================

    # 防止标题、坐标轴文字重叠。
    plt.tight_layout()

    # =========================
    # 显示图像
    # =========================

    plt.show()

    print(f"{symbol} 技术指标图绘制完成")


# =========================
# 主程序入口
# =========================

if __name__ == "__main__":

    # 修改这里即可切换不同 ETF / 股票。
    plot_indicators("sh510310")