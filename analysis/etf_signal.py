"""基于技术指标给 ETF 打分，筛选值得关注的标的。"""

import pandas as pd
from pathlib import Path

# =========================
# 判断ETF值得关注的打分系统
# =========================
def check_signal(filepath):
    # 从文件名推导 ETF 代码，例如 sh510310_indicators.csv -> sh510310。
    symbol = filepath.stem.replace("_indicators", "")

    # 读取指标文件，并按日期排序，确保 iloc[-1] 是最新一行。
    df = pd.read_csv(filepath)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # iloc[-1] 表示最后一行，也就是最新交易日。
    latest = df.iloc[-1]

    # score 是简单打分器；每满足一个条件加 1 分。
    score = 0

    # =========================
    # 打分规则
    # =========================
    # K < 20：KDJ 处于较低位置，常被视为偏超卖。
    if latest["K"] < 20:
        score += 1

    # J < 0：J 线更敏感，低于 0 表示短期可能过冷。
    if latest["J"] < 0:
        score += 1

    # CCI < -100：常用于识别价格偏离均值较多的情况。
    if latest["CCI"] < -100:
        score += 1

    # 收盘价接近布林下轨；1.01 是容忍度，可按策略偏好调整。
    if latest["close"] <= latest["BOLL_LOWER"] * 1.01:
        score += 1

    # MA20 > MA60：短期均线高于中期均线，表示趋势相对更强。
    if latest["MA20"] > latest["MA60"]:
        score += 1

    # 成交量高于 5 日均量，表示当天交易相对活跃。
    if latest["volume"] > latest["VOL5"]:
        score += 1
    
    # =========================
    # 返回字典；后面可以很方便地转成 DataFrame。
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
    # 主程序：扫描 data 文件夹下所有指标文件。
    data_dir = Path("data")
    indicator_files = data_dir.glob("*_indicators.csv")

    # signals 用来收集每个文件的评分结果。
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

    # 按 Score 排序（从高到低），高分排在前面。
    signal_df = signal_df.sort_values("Score", ascending=False)

    # 这里显示全部结果；如果标的很多，可以改成 signal_df.head(10)。
    print(signal_df.to_string(index=False))

    print("=" * 120)
