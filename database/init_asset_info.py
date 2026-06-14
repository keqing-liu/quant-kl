"""初始化 asset_info 表。

这个脚本用于把项目关注标的的基础信息写入 SQLite 数据库。

运行方式：

    python -m database.init_asset_info

注意：
1. asset_info 不是行情数据，不从 akshare 自动下载；
2. 它是你自己维护的资产基础档案；
3. price_data 仍然由 data_manager / data_fetch 负责下载；
4. 本脚本只负责维护 symbol 对应的名称、资产类型、市场、数据源、基准等信息。
"""

from database.db_utils import get_connection, initialize_database


# =========================
# 资产基础信息
# =========================

ASSETS = [
    # =========================
    # A 股宽基 / 行业 / 主题 ETF
    # =========================
    {
        "symbol": "sh510310",
        "name": "沪深300ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": "sh000300",
        "benchmark_name": "沪深300指数",
        "is_active": 1,
        "note": "A股大盘宽基ETF",
    },
    {
        "symbol": "sh510100",
        "name": "上证50ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": "sh000016",
        "benchmark_name": "上证50指数",
        "is_active": 1,
        "note": "A股大盘蓝筹ETF",
    },
    {
        "symbol": "sh510880",
        "name": "红利ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": "sh000015",
        "benchmark_name": "上证红利指数",
        "is_active": 1,
        "note": "A股红利风格ETF",
    },
    {
        "symbol": "sh512800",
        "name": "银行ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": "sh399986",
        "benchmark_name": "中证银行指数",
        "is_active": 1,
        "note": "A股银行行业ETF",
    },
    {
        "symbol": "sh516130",
        "name": "消费龙头ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": None,
        "benchmark_name": "消费龙头指数",
        "is_active": 1,
        "note": "A股消费主题ETF",
    },
    {
        "symbol": "sh512100",
        "name": "中证1000ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": "sh000852",
        "benchmark_name": "中证1000指数",
        "is_active": 1,
        "note": "A股小盘宽基ETF",
    },
    {
        "symbol": "sh588080",
        "name": "科创50ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": "sh000688",
        "benchmark_name": "科创50指数",
        "is_active": 1,
        "note": "科创板宽基ETF",
    },
    {
        "symbol": "sh513010",
        "name": "恒生科技ETF",
        "asset_type": "ETF",
        "asset_class": "EQUITY",
        "market": "HK",
        "data_source": "akshare_sina",
        "benchmark_symbol": None,
        "benchmark_name": "恒生科技指数",
        "is_active": 1,
        "note": "港股科技主题ETF",
    },

    # =========================
    # 商品 / 黄金 ETF
    # =========================
    {
        "symbol": "sh518880",
        "name": "黄金ETF",
        "asset_type": "COMMODITY_ETF",
        "asset_class": "COMMODITY",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": None,
        "benchmark_name": "黄金现货价格",
        "is_active": 1,
        "note": "黄金资产ETF，偏避险属性",
    },

    # =========================
    # 债券 ETF
    # =========================
    {
        "symbol": "sh511010",
        "name": "国债ETF",
        "asset_type": "BOND_ETF",
        "asset_class": "BOND",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": None,
        "benchmark_name": "国债相关指数",
        "is_active": 1,
        "note": "国债ETF，偏防御资产",
    },
    {
        "symbol": "sh511020",
        "name": "活跃国债ETF",
        "asset_type": "BOND_ETF",
        "asset_class": "BOND",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": None,
        "benchmark_name": "活跃国债相关指数",
        "is_active": 1,
        "note": "活跃国债ETF，偏防御资产",
    },
    {
        "symbol": "sh511260",
        "name": "十年国债ETF",
        "asset_type": "BOND_ETF",
        "asset_class": "BOND",
        "market": "CN",
        "data_source": "akshare_sina",
        "benchmark_symbol": None,
        "benchmark_name": "10年期国债相关指数",
        "is_active": 1,
        "note": "10年国债ETF，常用于股债轮动防御资产",
    },

    # =========================
    # A 股个股
    # =========================
    {
        "symbol": "sh600519",
        "name": "贵州茅台",
        "asset_type": "STOCK",
        "asset_class": "EQUITY",
        "market": "CN",
        "data_source": "akshare",
        "benchmark_symbol": "sh000300",
        "benchmark_name": "沪深300指数",
        "is_active": 1,
        "note": "A股白酒龙头公司",
    },

    # =========================
    # 美国 ETF
    # =========================
    {
        "symbol": "us_spy",
        "name": "SPDR S&P 500 ETF",
        "asset_type": "US_ETF",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance",
        "benchmark_symbol": "us_spy",
        "benchmark_name": "S&P 500",
        "is_active": 1,
        "note": "美国 S&P 500 ETF",
    },
    {
        "symbol": "us_voo",
        "name": "Vanguard S&P 500 ETF",
        "asset_type": "US_ETF",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance",
        "benchmark_symbol": "us_spy",
        "benchmark_name": "S&P 500",
        "is_active": 0,
        "note": "与 SPY 重复，当前不纳入日常观察",
    },
    {
        "symbol": "us_qqq",
        "name": "Invesco QQQ Trust",
        "asset_type": "US_ETF",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance",
        "benchmark_symbol": "us_qqq",
        "benchmark_name": "Nasdaq 100",
        "is_active": 1,
        "note": "美国 Nasdaq 100 ETF",
    },

    # =========================
    # 美国指数
    # =========================
    {
        "symbol": "stooq_ndq",
        "name": "Nasdaq Composite",
        "asset_type": "US_INDEX",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "stooq",
        "benchmark_symbol": "stooq_ndq",
        "benchmark_name": "Nasdaq Composite",
        "is_active": 1,
        "note": "Stooq 符号 ^ndq，配置中写作 NDQ",
    },

    # =========================
    # 美国股票
    # =========================
    {
        "symbol": "us_aapl",
        "name": "Apple",
        "asset_type": "US_STOCK",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance/sec_companyfacts",
        "benchmark_symbol": "us_spy",
        "benchmark_name": "S&P 500",
        "is_active": 1,
        "note": "美国上市公司",
    },
    {
        "symbol": "us_msft",
        "name": "Microsoft",
        "asset_type": "US_STOCK",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance/sec_companyfacts",
        "benchmark_symbol": "us_spy",
        "benchmark_name": "S&P 500",
        "is_active": 1,
        "note": "美国上市公司",
    },
    {
        "symbol": "us_nvda",
        "name": "NVIDIA",
        "asset_type": "US_STOCK",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance/sec_companyfacts",
        "benchmark_symbol": "us_spy",
        "benchmark_name": "S&P 500",
        "is_active": 1,
        "note": "美国上市公司",
    },
    {
        "symbol": "us_brk_b",
        "name": "Berkshire Hathaway",
        "asset_type": "US_STOCK",
        "asset_class": "EQUITY",
        "market": "US",
        "data_source": "yfinance/sec_companyfacts",
        "benchmark_symbol": "us_spy",
        "benchmark_name": "S&P 500",
        "is_active": 1,
        "note": "美国上市公司",
    },
]


# =========================
# 初始化 asset_info
# =========================

def init_asset_info():
    """把 ASSETS 中的资产基础信息写入 asset_info 表。"""

    # 确保数据库基础表结构已经创建。
    initialize_database()

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT OR REPLACE INTO asset_info (
        symbol,
        name,
        asset_type,
        asset_class,
        market,
        data_source,
        benchmark_symbol,
        benchmark_name,
        is_active,
        note
    )
    VALUES (
        :symbol,
        :name,
        :asset_type,
        :asset_class,
        :market,
        :data_source,
        :benchmark_symbol,
        :benchmark_name,
        :is_active,
        :note
    )
    """

    cursor.executemany(sql, ASSETS)

    conn.commit()
    conn.close()

    print(f"asset_info 初始化完成：{len(ASSETS)} 个资产")


# =========================
# 主程序
# =========================

if __name__ == "__main__":
    init_asset_info()
