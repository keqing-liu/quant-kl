"""从 SQLite 读取价格数据，计算技术指标，并保存回 SQLite。

这个文件是项目的数据分析核心。pandas 负责表格计算，numpy 负责数值计算，
SQLite 负责持久化保存结果。
"""

import pandas as pd
import numpy as np

from database.db_utils import get_connection, initialize_database


# =========================
# 读取数据库中的所有 symbol
# =========================

def get_all_symbols():

    # 连接数据库，读取 price_data 表里出现过的所有 symbol。
    conn = get_connection()

    # pd.read_sql 可以把 SQL 查询结果直接变成 DataFrame。
    df = pd.read_sql("""
        SELECT DISTINCT symbol
        FROM price_data
        ORDER BY symbol
    """, conn)

    conn.close()

    # df["symbol"] 是一列 Series；tolist() 转成普通 Python 列表。
    return df["symbol"].tolist()


# =========================
# 读取单个 symbol 的价格数据
# =========================

def load_price_data(symbol):

    conn = get_connection()

    # WHERE symbol = ? 是参数化查询；params=(symbol,) 里的逗号表示单元素元组。
    df = pd.read_sql("""
        SELECT *
        FROM price_data
        WHERE symbol = ?
        ORDER BY date
    """, conn, params=(symbol,))

    conn.close()

    return df


# =========================
# 计算单个 ETF / 股票指标
# =========================

def calculate_indicators(symbol):

    print(f"开始计算 {symbol} 指标...")

    # 先把该标的全部价格数据取出来。
    df = load_price_data(symbol)

    if df.empty:
        print(f"{symbol} 没有价格数据，跳过")
        return None

    # 日期转换：SQLite 中读出来通常是字符串，转 datetime 后方便排序和比较。
    df["date"] = pd.to_datetime(df["date"])

    # reset_index(drop=True) 重新生成 0,1,2... 的行号，方便后面用 loc[i]。
    df = df.sort_values("date").reset_index(drop=True)

    # =========================
    # MA20 / MA50 / MA60
    # =========================

    # rolling(window=N).mean() 是移动平均；前 N-1 行因为数据不足会是 NaN。
    df["MA20"] = df["close"].rolling(window=20).mean()
    df["MA50"] = df["close"].rolling(window=50).mean()
    df["MA60"] = df["close"].rolling(window=60).mean()

    # =========================
    # Daily Return
    # =========================

    # pct_change() 计算相邻两天的百分比变化：(今天/昨天 - 1)。
    df["RETURN"] = df["close"].pct_change()

    # =========================
    # 波动率
    # =========================

    # std() 是标准差；这里用收益率标准差近似衡量波动率。
    df["VOLATILITY20"] = df["RETURN"].rolling(window=20).std()
    df["VOLATILITY252"] = df["RETURN"].rolling(window=252).std()

    # =========================
    # Bollinger Bands
    # =========================

    # 布林带通常用 20 日均线 +/- 2 倍标准差。
    df["STD20"] = df["close"].rolling(window=20).std()

    df["BOLL_UPPER"] = df["MA20"] + 2 * df["STD20"]
    df["BOLL_LOWER"] = df["MA20"] - 2 * df["STD20"]

    # =========================
    # Volume
    # =========================

    # 成交量均线，用于观察近期成交是否放大或缩小。
    df["VOL5"] = df["volume"].rolling(window=5).mean()
    df["VOL20"] = df["volume"].rolling(window=20).mean()

    # =========================
    # KDJ
    # =========================

    # KDJ 的 RSV 使用最近 9 日最高价和最低价衡量收盘价所处位置。
    low_n = df["low"].rolling(window=9).min()
    high_n = df["high"].rolling(window=9).max()

    df["RSV"] = (
        (df["close"] - low_n)
        / (high_n - low_n)
    ) * 100

    # 前几行缺少 9 日窗口会得到 NaN，这里用中性值 50 填充。
    df["RSV"] = df["RSV"].fillna(50)

    # K、D 设置初始值为 50，然后用循环递推。
    df["K"] = 50.0
    df["D"] = 50.0

    for i in range(1, len(df)):

        # loc[i, "K"] 表示按“行标签 i + 列名 K”定位单个单元格。
        df.loc[i, "K"] = (
            2 / 3 * df.loc[i - 1, "K"]
            + 1 / 3 * df.loc[i, "RSV"]
        )

        df.loc[i, "D"] = (
            2 / 3 * df.loc[i - 1, "D"]
            + 1 / 3 * df.loc[i, "K"]
        )

    # J 是 KDJ 中更敏感的一条线。
    df["J"] = 3 * df["K"] - 2 * df["D"]

    # =========================
    # CCI
    # =========================

    # TP: Typical Price，典型价格 = (最高 + 最低 + 收盘) / 3。
    tp = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    # 典型价格的 14 日均线。
    ma_tp = tp.rolling(window=14).mean()

    # mean deviation：平均绝对偏差。lambda x 是对每个滚动窗口执行的小函数。
    md = tp.rolling(window=14).apply(
        lambda x: np.abs(x - x.mean()).mean(),
        raw=True
    )

    df["CCI"] = (
        tp - ma_tp
    ) / (0.015 * md)

    # =========================
    # 只保留 indicators 表需要的列
    # =========================

    indicator_df = df[[
        "symbol",
        "date",

        "MA20",
        "MA50",
        "MA60",
        "RETURN",

        "VOLATILITY20",
        "VOLATILITY252",

        "STD20",
        "BOLL_UPPER",
        "BOLL_LOWER",

        "VOL5",
        "VOL20",

        "RSV",
        "K",
        "D",
        "J",

        "CCI"
    ]].copy()

    # SQLite 没有真正的日期类型；保存成 YYYY-MM-DD 文本最简单清晰。
    indicator_df["date"] = indicator_df["date"].dt.strftime("%Y-%m-%d")

    print(f"{symbol} 指标计算完成")

    return indicator_df


# =========================
# 保存指标到 SQLite
# =========================

def save_indicators(indicator_df):

    # 没有数据时直接返回，避免后面的 SQL 写入报错。
    if indicator_df is None or indicator_df.empty:
        return

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    INSERT OR REPLACE INTO indicators (
        symbol,
        date,

        MA20,
        MA50,
        MA60,
        RETURN,

        VOLATILITY20,
        VOLATILITY252,

        STD20,
        BOLL_UPPER,
        BOLL_LOWER,

        VOL5,
        VOL20,

        RSV,
        K,
        D,
        J,

        CCI
    )
    VALUES (
        ?, ?,
        ?, ?, ?, ?,
        ?, ?,
        ?, ?, ?,
        ?, ?,
        ?, ?, ?, ?,
        ?
    )
    """


    # itertuples 比逐行 iloc 更适合批量写入；name=None 返回普通元组。
    data = list(
        indicator_df.itertuples(
            index=False,
            name=None
        )
    )

    # executemany 一次性执行多行插入，比 for 循环一行行 execute 更高效。
    cursor.executemany(sql, data)

    conn.commit()
    conn.close()

    print(f"写入 indicators 表完成：{len(indicator_df)} 行")


def run_indicator_analysis():

    # 先确保 price_data 和 indicators 等基础表存在。
    initialize_database()

    # 从 price_data 表自动发现要计算的标的。
    symbols = get_all_symbols()

    for symbol in symbols:

        try:

            indicator_df = calculate_indicators(symbol)

            save_indicators(indicator_df)

        except Exception as e:
            # 单个 symbol 出错不影响其他 symbol 继续计算。
            print(f"{symbol} 指标计算失败: {e}")

# =========================
# 主程序
# =========================

if __name__ == "__main__":

    run_indicator_analysis()