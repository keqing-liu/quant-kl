import akshare as ak
import pandas as pd

def fetch_stock(symbol):

    df = ak.stock_zh_a_daily(
        symbol=symbol,
        adjust="qfq"
    )

    filename = f"data/{symbol}.csv"

    df.to_csv(filename, index=False)

    print(f"{symbol} 股票数据保存完成")