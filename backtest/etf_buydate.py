"""扫描历史数据中出现买入信号的日期。

这个脚本不做完整买卖回测，只回答一个问题：
“历史上哪些日期满足我定义的买入条件？”
"""

import pandas as pd
from pathlib import Path

# =========================
# 判断买入信号
# =========================

def buy_signal(row):

    # row 是 DataFrame 的一行，类似 Matlab table 中的一行记录。
    # 这里所有条件同时成立时才返回 True。
    return (

        row["K"] < 10
        and row["J"] < 0
        and row["CCI"] < -100
        and row["close"]
        <= row["BOLL_LOWER"] * 1.005

    )

# =========================
# 扫描单个ETF
# =========================

def scan_signals(filepath):

    # 从指标文件名推导 ETF 代码。
    symbol = filepath.stem.replace(
        "_indicators",
        ""
    )

    # 读取指标 CSV。
    df = pd.read_csv(filepath)

    # 转换日期类型，方便排序和格式化输出。
    df["date"] = pd.to_datetime(
        df["date"]
    )

    # 按日期排序并重置行号，保证后面的 for i in range(len(df)) 顺序正确。
    df = df.sort_values(
        "date"
    ).reset_index(drop=True)

    # signals 用来收集所有符合条件的日期。
    signals = []

    for i in range(len(df)):

        # iloc[i] 按整数位置取第 i 行。
        row = df.iloc[i]

        if buy_signal(row):

            # append 一个字典；最后可以统一转成 DataFrame。
            signals.append({

                "ETF": symbol,

                "Date": row["date"].strftime(
                    "%Y-%m-%d"
                ),

                "Close": round(
                    row["close"], 2
                ),

                "K": round(
                    row["K"], 2
                ),

                "D": round(
                    row["D"], 2
                ),

                "J": round(
                    row["J"], 2
                ),

                "CCI": round(
                    row["CCI"], 2
                ),

                "BOLL_LOWER": round(
                    row["BOLL_LOWER"], 2
                )

            })

    return signals

# =========================
# 主程序
# =========================

if __name__ == "__main__":

    data_dir = Path("data")

    # 找到所有以 _indicators.csv 结尾的文件。
    indicator_files = data_dir.glob(
        "*_indicators.csv"
    )

    all_signals = []

    for filepath in indicator_files:

        try:

            signals = scan_signals(
                filepath
            )

            all_signals.extend(
                signals
            )

        except Exception as e:

            print(
                f"{filepath.name} 扫描失败: {e}"
            )

    # =========================
    # 输出结果
    # =========================

    if len(all_signals) == 0:

        print("没有发现交易信号")

    else:

        # 把字典列表转成表格，方便排序和打印。
        signal_df = pd.DataFrame(
            all_signals
        )

        # 按信号日期从早到晚排序。
        signal_df = signal_df.sort_values(
            "Date"
        )

        print("\n")
        print("=" * 120)
        print("交易信号")
        print("=" * 120)

        print(
            signal_df.to_string(
                index=False
            )
        )

        print("=" * 120)
