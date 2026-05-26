"""把指标 CSV 的最近几天数据打印成摘要表。

这个脚本主要用于快速查看每个 ETF 最近的技术指标状态。
"""

import pandas as pd
from pathlib import Path

# =========================
# 输出单个ETF摘要
# =========================

def print_summary(filepath):

    # filepath 是 Path 对象；stem 是不带扩展名的文件名。
    # 例如 sh510310_indicators.csv -> sh510310_indicators -> sh510310。
    symbol = filepath.stem.replace("_indicators", "")

    print("\n")
    print("=" * 80)
    print(f"{symbol} 最近5个交易日技术指标")
    print("=" * 80)

    # 读取 CSV 为 DataFrame，类似 Matlab 里的 readtable。
    df = pd.read_csv(filepath)

    # 把字符串日期转为 datetime，后面排序和格式化更可靠。
    df["date"] = pd.to_datetime(df["date"])

    # 按日期从早到晚排序，保证 tail(5) 真的是最近 5 天。
    df = df.sort_values("date")

    # tail(5) 取最后 5 行；iloc[::-1] 把顺序反过来，让最新日期显示在最上面。
    recent = df.tail(5).iloc[::-1]

    # 只展示最关心的列，避免终端输出太宽。
    columns = [
        "date",
        "close",
        "VOL5",
        "VOL20",
        "MA20",
        "MA60",
        "BOLL_UPPER",
        "BOLL_LOWER",
        "K",
        "D",
        "J",
        "CCI"
    ]

    # round(2) 对数值列保留两位小数；日期列不会受影响。
    recent = recent[columns].round(2)

    # to_string(index=False) 打印表格时隐藏 pandas 自动行号。
    print(recent.to_string(index=False))


# =========================
# 主程序
# =========================

if __name__ == "__main__":

    # Path("data") 指向项目里的 data 文件夹。
    data_dir = Path("data")

    # glob("*_indicators.csv") 找到所有指标文件；返回的是一个可迭代对象。
    indicator_files = data_dir.glob("*_indicators.csv")

    for filepath in indicator_files:

        try:

            print_summary(filepath)

        except Exception as e:
            # 单个文件出错时只打印错误，不影响其他文件继续输出。
            print(f"{filepath.name} 输出失败: {e}")
