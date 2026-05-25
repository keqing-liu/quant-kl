import pandas as pd
from pathlib import Path

# =========================
# 判断ETF值得关注的打分系统
# =========================
def check_signal(filepath):
    symbol = filepath.stem.replace("_indicators", "")

    # 读取数据
    df = pd.read_csv(filepath)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    latest = df.iloc[-1]

    score = 0

    # =========================
    # 打分规则
    # =========================
    # K < 20
    if latest["K"] < 20:
        score += 1

    # J < 0
    if latest["J"] < 0:
        score += 1

    # CCI < -100
    if latest["CCI"] < -100:
        score += 1

    # 收盘价接近布林下轨（这里1.02可调整）
    if latest["close"] <= latest["BOLL_LOWER"] * 1.01:
        score += 1

    # MA20 > MA60 （短期上升趋势）
    if latest["MA20"] > latest["MA60"]:
        score += 1

    if latest["volume"]>latest["VOL5"]:
        score += 1
    
    # =========================
    # 输出包含分数的字典
    # =========================
    return {
        "ETF": symbol,
        "Date": latest["date"].strftime("%Y-%m-%d"),
        "Close": round(latest["close"], 2),
        "MA20": round(latest["MA20"], 2),
        "MA60": round(latest["MA60"], 2),
        "BOLL_UPPER": round(latest["BOLL_UPPER"], 2),
        "BOLL_LOWER": round(latest["BOLL_LOWER"], 2),
        "K": round(latest["K"], 2),
        "D": round(latest["D"], 2),
        "J": round(latest["J"], 2),
        "CCI": round(latest["CCI"], 2),
        "Score": score
    }


# =========================
# 主程序
# =========================
if __name__ == "__main__":
    data_dir = Path("data")
    indicator_files = data_dir.glob("*_indicators.csv")

    signals = []

    for filepath in indicator_files:
        try:
            result = check_signal(filepath)
            signals.append(result)
        except Exception as e:
            print(f"{filepath.name} 分析失败: {e}")

    # =========================
    # 输出结果
    # =========================
    print("\n")
    print("=" * 120)
    print("ETF 技术指标打分（分数越高越值得关注）")
    print("=" * 120)

    signal_df = pd.DataFrame(signals)

    # 按 Score 排序（从高到低）
    signal_df = signal_df.sort_values("Score", ascending=False)

    # 显示前 10 或全部
    print(signal_df.to_string(index=False))

    print("=" * 120)