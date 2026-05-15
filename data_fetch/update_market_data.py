from config.watchlist import WATCHLIST
from data_fetch.fetch_etf import fetch_etf
from data_fetch.fetch_stock import fetch_stock


# 获取 ETF 列表
etf_list  =  WATCHLIST["ETF"]
stock_list = WATCHLIST["STOCK"]

# 循环下载
for symbol in etf_list:

    try:
        fetch_etf(symbol)

    except Exception as e:
        print(f"{symbol} 下载失败: {e}")

for symbol in stock_list:

    try:
        fetch_stock(symbol)

    except Exception as e:
        print(f"股票 {symbol} 下载失败: {e}")