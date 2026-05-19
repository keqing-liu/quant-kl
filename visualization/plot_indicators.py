import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# =========================
# 读取指标文件
# =========================

symbol = "sh510310"

filepath = Path(f"data/{symbol}_indicators.csv")

df = pd.read_csv(filepath)

# 日期转换
df["date"] = pd.to_datetime(df["date"])

# =========================
# 创建画布
# =========================

fig = plt.figure(figsize=(16, 12))

# =========================
# 子图1：价格 + 均线 + 布林带
# =========================

ax1 = plt.subplot(3, 1, 1)

ax1.plot(
    df["date"],
    df["close"],
    label="Close"
)

ax1.plot(
    df["date"],
    df["MA20"],
    label="MA20"
)

ax1.plot(
    df["date"],
    df["MA60"],
    label="MA60"
)

ax1.plot(
    df["date"],
    df["BOLL_UPPER"],
    linestyle="--",
    label="BOLL Upper"
)

ax1.plot(
    df["date"],
    df["BOLL_LOWER"],
    linestyle="--",
    label="BOLL Lower"
)

ax1.set_title(f"{symbol} Price & Bollinger Bands")

ax1.legend()

ax1.grid(True)

# =========================
# 子图2：KDJ
# =========================

ax2 = plt.subplot(3, 1, 2)

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

ax3 = plt.subplot(3, 1, 3)

ax3.plot(
    df["date"],
    df["CCI"],
    label="CCI"
)

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
# 自动调整布局
# =========================

plt.tight_layout()

# =========================
# 显示图像
# =========================

plt.show()