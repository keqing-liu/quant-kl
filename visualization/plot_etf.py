"""用 mplfinance 绘制 ETF K 线图。

mplfinance 要求列名为 Open/High/Low/Close/Volume，并且日期作为 index。
"""

import pandas as pd
import mplfinance as mpf

# 读取普通行情 CSV。
df = pd.read_csv("data/sh510310.csv")

# 把 date 列转成 datetime，后面才能设置为时间索引。
df["date"] = pd.to_datetime(df["date"])

# 设置 date 为索引；inplace=True 表示直接修改 df 本身。
df.set_index("date", inplace=True)

# 重命名列（非常重要）：mplfinance 识别的是英文首字母大写列名。
df.rename(columns={
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "volume": "Volume"
}, inplace=True)

# 画蜡烛图；mav=(5, 20) 表示同时画 5 日和 20 日均线。
mpf.plot(
    df,
    type="candle",
    mav=(5, 20),
    volume=True
)
