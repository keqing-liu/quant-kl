"""批量下载 watchlist 里的 ETF 和股票数据到 CSV。

注意：这个脚本导入了 fetch_etf，但当前 fetch_etf.py 中的函数名是
download_etf_data；如果要运行这个脚本，需要先统一函数名。
"""

from config.watchlist import WATCHLIST
from data_fetch.fetch_etf import fetch_etf
from data_fetch.fetch_stock import fetch_stock


# 从配置字典里取出两个列表：ETF 和 STOCK。
etf_list = WATCHLIST["ETF"]
stock_list = WATCHLIST["STOCK"]

# 逐个下载 ETF。try/except 保证一只失败不会中断整个批处理。
for symbol in etf_list:

    try:
        fetch_etf(symbol)

    except Exception as e:
        print(f"{symbol} 下载失败: {e}")

# 逐个下载股票。
for symbol in stock_list:

    try:
        fetch_stock(symbol)

    except Exception as e:
        print(f"股票 {symbol} 下载失败: {e}")
