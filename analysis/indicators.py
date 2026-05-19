import pandas as pd
from pathlib import Path

# =========================
# 计算单个ETF指标
# =========================

def calculate_indicators(filepath):

    # 文件名
    symbol = filepath.stem

    print(f"开始计算 {symbol} 指标...")

    # 读取数据
    df = pd.read_csv(filepath)

    # 日期转换
    df["date"] = pd.to_datetime(df["date"])

    # =========================
    # MA20 & MA60
    # =========================

    df["MA20"] = df["close"].rolling(window=20).mean()

    df["MA60"] = df["close"].rolling(window=60).mean()

    # =========================
    # Bollinger Bands
    # =========================

    df["STD20"] = df["close"].rolling(window=20).std()

    df["BOLL_UPPER"] = (
        df["MA20"]
        + 2 * df["STD20"]
    )

    df["BOLL_LOWER"] = (
        df["MA20"]
        - 2 * df["STD20"]
    )

    # =========================
    # KDJ
    # =========================

    low_n = df["low"].rolling(window=9).min()

    high_n = df["high"].rolling(window=9).max()

    df["RSV"] = (
        (df["close"] - low_n)
        / (high_n - low_n)
    ) * 100

    df["RSV"] = df["RSV"].fillna(50)

    df["K"] = 50.0
    df["D"] = 50.0

    for i in range(1, len(df)):

        df.loc[i, "K"] = (
            2 / 3 * df.loc[i - 1, "K"]
            + 1 / 3 * df.loc[i, "RSV"]
        )

        df.loc[i, "D"] = (
            2 / 3 * df.loc[i - 1, "D"]
            + 1 / 3 * df.loc[i, "K"]
        )

    df["J"] = (
        3 * df["K"]
        - 2 * df["D"]
    )

    # =========================
    # CCI
    # =========================

    tp = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    # TP均线
    ma_tp = tp.rolling(window=14).mean()

    # Mean Deviation
    md = tp.rolling(window=14).apply(
        lambda x: abs(x - x.mean()).mean(),
        raw=True
    )


    # CCI
    df["CCI"] = (
        tp - ma_tp
    ) / (0.015 * md)

    # =========================
    # 保存结果
    # =========================

    output_path = Path(
        f"data/{symbol}_indicators.csv"
    )

    df.to_csv(output_path, index=False)

    print(f"{symbol} 指标计算完成")


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    data_dir = Path("data")

    # 找到所有csv文件
    csv_files = data_dir.glob("*.csv")

    for filepath in csv_files:

        # 避免重复处理 indicator 文件
        if "indicator" in filepath.stem:
            continue

        try:

            calculate_indicators(filepath)

        except Exception as e:

            print(f"{filepath.name} 处理失败: {e}")