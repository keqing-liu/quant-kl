import pandas as pd
import mplfinance as mpf

# 读取 CSV
df = pd.read_csv("data/sh510310.csv")

# 日期转换
df["date"] = pd.to_datetime(df["date"])

# 设置 index
df.set_index("date", inplace=True)

# 重命名列（非常重要）
df.rename(columns={
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume"
}, inplace=True)

# 画图
mpf.plot(
    df,
    type="candle",
    mav=(5, 20),
    volume=True
)