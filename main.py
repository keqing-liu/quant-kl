"""项目入口：初始化数据库，并按 watchlist 更新 ETF 行情。

如果你习惯 Matlab，可以把这个文件理解成一个主脚本（main script）：
它负责调用别的模块里的函数/类，自己不做复杂计算。
"""

# 从配置文件导入关注列表；Python 的 import 类似 Matlab 里调用其他 .m 文件。
from config.watchlist import WATCHLIST

# DataManager 是自己写的类，集中管理“下载数据并写入数据库”的流程。
from data_manager.data_manager import DataManager

# initialize_database 会创建 SQLite 表；如果表已经存在，不会重复创建。
from database.db_utils import initialize_database

from analysis.indicators import (
    run_indicator_analysis
)

# 第一步：确保数据库和需要的表已经准备好。
initialize_database()

# 创建 DataManager 的一个实例；后面通过 manager.update_etf(...) 调用它的方法。
manager = DataManager()

# WATCHLIST 是一个字典，"ETF" 这个键对应 ETF 代码列表。
etf_list = WATCHLIST["ETF"]
stock_list = WATCHLIST["STOCK"]
us_etf_list = WATCHLIST.get("US_ETF", [])
us_stock_list = WATCHLIST.get("US_STOCK", [])
us_index_list = WATCHLIST.get("US_INDEX", [])
us_market_indicator_list = WATCHLIST.get("US_MARKET_INDICATOR", [])

# 遍历 ETF 列表，逐个更新。
for symbol in etf_list:

    try:
        # 单个 ETF 失败时，不影响后面的 ETF 继续更新。
        manager.update_etf(symbol)

    except Exception as e:
        # f-string 用来把变量嵌入字符串，类似 Matlab 里 sprintf 的用途。
        print(f"{symbol} 更新失败: {e}")

for symbol in stock_list:

    try:
        manager.update_stock(symbol)

    except Exception as e:
        print(f"股票 {symbol} 更新失败: {e}")

for ticker in us_etf_list:

    try:
        manager.update_us_etf(ticker)

    except Exception as e:
        print(f"美国 ETF {ticker} 更新失败: {e}")

for ticker in us_stock_list:

    try:
        manager.update_us_stock(ticker)

    except Exception as e:
        print(f"美国股票 {ticker} 更新失败: {e}")

for symbol in us_index_list:

    try:
        manager.update_us_index(symbol)

    except Exception as e:
        print(f"美国指数 {symbol} 更新失败: {e}")

for symbol in us_market_indicator_list:

    try:
        manager.update_us_market_indicator(symbol)

    except Exception as e:
        print(f"美国市场指标 {symbol} 更新失败: {e}")

# 计算技术指标

run_indicator_analysis()
