"""从 SQLite 数据库读取 ETF / 股票行情，并使用 mplfinance 绘制 K 线图。

mplfinance 要求：
1. 日期列作为 index
2. OHLCV 列名必须是：
   Open / High / Low / Close / Volume
"""

import pandas as pd
import mplfinance as mpf

from database.db_utils import get_connection


# =========================
# 从 SQLite 读取行情数据
# =========================

def load_price_data(symbol):

    # 获取 SQLite 数据库连接。
    conn = get_connection()

    # 从 price_data 表读取指定 symbol 的历史行情。
    # ORDER BY date 保证时间从旧到新排序。
    df = pd.read_sql("""

        SELECT *
        FROM price_data
        WHERE symbol = ?
        ORDER BY date

    """, conn, params=(symbol,))

    conn.close()

    return df


# =========================
# 绘制 K 线图
# =========================

def plot_etf(symbol):

    print(f"开始绘制 {symbol} K线图...")

    # 从数据库读取数据。
    df = load_price_data(symbol)

    # DataFrame 为空时直接返回，避免后面绘图报错。
    if df.empty:

        print(f"{symbol} 没有数据")

        return

    # SQLite 中 date 通常保存为文本；
    # 转成 datetime 后才能作为时间索引。
    df["date"] = pd.to_datetime(df["date"])

    # 设置日期为 index。
    # mplfinance 要求时间序列 index 必须是 DatetimeIndex。
    df.set_index("date", inplace=True)

    # mplfinance 识别的是标准 OHLCV 英文列名。
    df.rename(columns={

        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume"

    }, inplace=True)

    # =========================
    # 绘制蜡烛图
    # =========================

    mpf.plot(

        df,

        # candle = K线图
        type="candle",

        # 显示成交量子图
        volume=True,

        # 均线
        mav=(20, 60),

        # 图标题
        title=f"{symbol} Candlestick Chart",

        # 使用 Yahoo 风格配色
        style="yahoo",

        # 图像大小
        figsize=(12, 8)

    )

    print(f"{symbol} K线图绘制完成")


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    plot_etf("sh510310")