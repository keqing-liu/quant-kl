"""项目关注标的列表。

WATCHLIST 是 Python 字典：左边的 "ETF"、"STOCK" 是键，
右边的 [...] 是列表。其他脚本会从这里读取要下载和分析的代码。
"""

WATCHLIST = {
    "ETF": [
        "sh510310",  # 沪深300指数
        "sh510100",  # 上证50指数
        "sh510880",  # 上证红利指数
        "sh512800",  # 中证银行指数
        "sh518880",  # 黄金现货指数
        "sh516130",  # 消费龙头指数
        "sh512100",  # 中证1000指数
        "sh588080",  # 科创50指数
        "sh513010",  # 恒生科技指数
        "sh511010",  # 国债ETF指数
        "sh511020",  # 活跃国债ETF指数
        "sh511260",  # 10年国债ETF指数
    ],

    "STOCK": [
        "sh600519",  # 贵州茅台
        "sz002594",  # 比亚迪
        "sz000333",  # 美的集团
        "sh603195",  # 公牛集团
    ],

    "US_ETF": [
        "SPY",  # SPDR S&P 500 ETF
        "VOO",  # Vanguard S&P 500 ETF
        "QQQ",  # Invesco QQQ Trust
        "SMH",  # VanEck Semiconductor ETF；Stooq 可下载的半导体风险代理
    ],

    "US_INDEX": [
        # Stooq 当前对 ^sox 返回空数据；如未来恢复覆盖，可在这里加入 "^sox"。
    ],

    "US_MARKET_INDICATOR": [
        "^vix",  # Cboe Volatility Index；使用 Cboe 官方日度 CSV
        "^vxn",  # Nasdaq-100 Volatility Index；使用 Cboe 官方日度 CSV
        "^vvix",  # Cboe VVIX Index；使用 Cboe 官方日度 CSV
        "^skew",  # Cboe SKEW Index；使用 Cboe 官方日度 CSV
    ],

    "US_STOCK": [
        "AAPL",  # Apple
        "MSFT",  # Microsoft
        "NVDA",  # NVIDIA
        "TSM",  # Taiwan Semiconductor ADR
        "AVGO",  # Broadcom
        "ASML",  # ASML ADR
        "AMD",  # Advanced Micro Devices
        "INTC",  # Intel
        "BRK-B",  # Berkshire Hathaway
    ],
}
