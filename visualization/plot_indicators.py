"""绘制 ETF 技术指标图。

matplotlib 的核心思想是：先创建画布 figure，再创建子图 axes，
然后把不同曲线 plot 到对应的 axes 上。
"""

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# =========================
# 读取指标文件
# =========================

# 要画图的 ETF 代码。
symbol = "sh510310"

# 指标文件路径。
filepath = Path(f"data/{symbol}_indicators.csv")

# 读取指标数据。
df = pd.read_csv(filepath)

# 日期转换，matplotlib 才能把横轴按时间正确显示。
df["date"] = pd.to_datetime(df["date"])

# =========================
# 创建画布
# =========================

# figsize 单位是英寸；这里创建一个 16 x 12 的大画布。
fig = plt.figure(figsize=(16, 12))

# =========================
# 子图1：价格 + 均线 + 布林带
# =========================

# 3 行 1 列的第 1 个子图。
ax1 = plt.subplot(3, 1, 1)

# 价格曲线。
ax1.plot(
    df["date"],
    df["close"],
    label="Close"
)

# 20 日均线。
ax1.plot(
    df["date"],
    df["MA20"],
    label="MA20"
)

# 60 日均线。
ax1.plot(
    df["date"],
    df["MA60"],
    label="MA60"
)

# 布林上轨。
ax1.plot(
    df["date"],
    df["BOLL_UPPER"],
    linestyle="--",
    label="BOLL Upper"
)

# 布林下轨。
ax1.plot(
    df["date"],
    df["BOLL_LOWER"],
    linestyle="--",
    label="BOLL Lower"
)

ax1.set_title(f"{symbol} Price & Bollinger Bands")

# legend 根据每条线的 label 显示图例。
ax1.legend()

# grid(True) 打开网格线，便于读数。
ax1.grid(True)

# =========================
# 子图2：KDJ
# =========================

# 3 行 1 列的第 2 个子图：KDJ。
ax2 = plt.subplot(3, 1, 2)

# K、D、J 三条线共用同一个坐标轴。
ax2.plot(
    df["date"],
    df["K"],
    label="K"
)

ax2.plot(
    df["date"],
    df["D"],
    label="D"
)

ax2.plot(
    df["date"],
    df["J"],
    label="J"
)

# 80 和 20 常用作 KDJ 的高低参考线。
ax2.axhline(
    80,
    linestyle="--"
)

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

# 3 行 1 列的第 3 个子图：CCI。
ax3 = plt.subplot(3, 1, 3)

ax3.plot(
    df["date"],
    df["CCI"],
    label="CCI"
)

# CCI 的 +/-100 常被用作强弱区间参考线。
ax3.axhline(
    100,
    linestyle="--"
)

ax3.axhline(
    -100,
    linestyle="--"
)

ax3.set_title("CCI")

ax3.legend()

ax3.grid(True)

# =========================
# 自动调整布局，减少标题和坐标轴文字重叠。
# =========================

plt.tight_layout()

# =========================
# 显示图像；在脚本环境中会弹出绘图窗口。
# =========================

plt.show()
