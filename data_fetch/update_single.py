"""下载单个 ETF 的临时测试脚本。

适合初学时单独运行，确认 akshare 能正常取数、CSV 能正常保存。
"""

import akshare as ak
import pandas as pd

# 获取 ETF 历史行情
df = ak.fund_etf_hist_sina(
    symbol="sh510310"
)

# head() 显示 DataFrame 前 5 行，常用于快速检查字段和数据格式。
print(df.head())

# 保存到 CSV；index=False 表示不保存左侧的行号。
df.to_csv("data/510310.csv", index=False)

print("数据下载完成！")
