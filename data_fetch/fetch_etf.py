import akshare as ak
import pandas as pd
from pathlib import Path

def fetch_etf(symbol):

    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)

    df = ak.fund_etf_hist_sina(
        symbol=symbol
    )

    filename = f"data/{symbol}.csv"

    df.to_csv(filename, index=False)

    print(f"{symbol} ETF 数据保存完成")