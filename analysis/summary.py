import pandas as pd
from pathlib import Path

# =========================
# 输出单个ETF摘要
# =========================

def print_summary(filepath):

    symbol = filepath.stem.replace("_indicators", "")

    print("\n")
    print("=" * 80)
    print(f"{symbol} 最近5个交易日技术指标")
    print("=" * 80)

    # 读取数据
    df = pd.read_csv(filepath)

    # 只保留最近5行
    df["date"] = pd.to_datetime(df["date"])

    # 按日期排序
    df = df.sort_values("date")

    # 最近5个交易日（最新在最上）
    recent = df.tail(5).iloc[::-1]

    # 选择需要的列
    columns = [
        "date",
        "close",
        "MA20",
        "MA60",
        "BOLL_UPPER",
        "BOLL_LOWER",
        "K",
        "D",
        "J",
        "CCI"
    ]

    # 保留两位小数
    recent = recent[columns].round(2)

    print(recent.to_string(index=False))


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    data_dir = Path("data")

    indicator_files = data_dir.glob("*_indicators.csv")

    for filepath in indicator_files:

        try:

            print_summary(filepath)

        except Exception as e:

            print(f"{filepath.name} 输出失败: {e}")