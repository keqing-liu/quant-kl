import akshare as ak
import pandas as pd

# 获取 ETF 历史行情
df = ak.fund_etf_hist_sina(
    symbol="sh510310"
)

# 显示前几行
print(df.head())

# 保存到 CSV
df.to_csv("data/510310.csv", index=False)

print("数据下载完成！")