"""股票数据下载脚本函数。

当前函数把单只 A 股的历史行情下载到 data/{symbol}.csv。
"""

def download_stock_data(symbol):
    import akshare as ak

    # stock_zh_a_daily 返回日线行情；adjust="qfq" 表示前复权价格。
    df = ak.stock_zh_a_daily(
        symbol=symbol,
        adjust="qfq"
    )

    # 只负责“下载并返回”，不在这里保存文件或写数据库，职责更清晰。
    return df
