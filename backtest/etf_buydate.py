import pandas as pd
from pathlib import Path

# =========================
# 判断买入信号
# =========================

def buy_signal(row):

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

    symbol = filepath.stem.replace(
        "_indicators",
        ""
    )

    df = pd.read_csv(filepath)

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df = df.sort_values(
        "date"
    ).reset_index(drop=True)

    signals = []

    for i in range(len(df)):

        row = df.iloc[i]

        if buy_signal(row):

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

        signal_df = pd.DataFrame(
            all_signals
        )

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