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
    # 如果收盘价高于50日均价 分数加1    
    if latest["close"] > latest["MA50"]:
        score += 1

    # 如果20日波动率小于年波动率，分数加1
    if latest["VOLATILITY20"] <= latest["VOLATILITY252"]:
        score += 1

    
    # =========================
    # 输出包含分数的字典
    # =========================
    return {
        "ETF": symbol,
        "Date": latest["date"].strftime("%Y-%m-%d"),
        "Close": round(latest["close"], 2),
        "MA50": round(latest["MA50"], 2),
        "VOLATILITY20": round(latest["VOLATILITY20"], 6),
        "VOLATILITY252": round(latest["VOLATILITY252"], 6),
        "Score": score
    }


# =========================
# 主程序
# =========================
if __name__ == "__main__":
    data_dir = Path("data")
    target_symbols = [
        "sh510310"
    ]

    indicator_files = [
        data_dir / f"{symbol}_indicators.csv"
        for symbol in target_symbols
    ]

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