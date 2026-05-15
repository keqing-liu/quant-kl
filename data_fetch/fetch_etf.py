import akshare as ak
import pandas as pd

def fetch_etf(symbol):

    df = ak.fund_etf_hist_sina(
        symbol=symbol
    )

    filename = f"data/{symbol}.csv"

    df.to_csv(filename, index=False)

    print(f"{symbol} ETF 数据保存完成")