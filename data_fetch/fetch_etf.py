"""ETF 数据下载函数。

akshare 是常用的中文金融数据接口库；这里用它从新浪接口取 ETF 历史行情。
"""

def download_etf_data(symbol):
    import akshare as ak

    # fund_etf_hist_sina 返回一个 pandas DataFrame，通常包含 date/open/high/low/close/volume。
    df = ak.fund_etf_hist_sina(
        symbol=symbol
    )

    # 只负责“下载并返回”，不在这里保存文件或写数据库，职责更清晰。
    return df
