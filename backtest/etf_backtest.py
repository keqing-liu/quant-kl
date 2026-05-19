import pandas as pd
from pathlib import Path

# =========================
# 买入信号
# =========================

def buy_signal(row):

    return (

        row["K"] < 15
        and row["J"] < 10
        and row["CCI"] < -120
        and row["MA20"] > row["MA60"]
        and row["close"]
        <= row["BOLL_LOWER"] * 1.005

    )

# =========================
# 回测单个ETF
# =========================

def backtest_etf(
    filepath,
    hold_days=15,
    stop_loss=-0.05,
    take_profit=0.10
):

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

    trades = []

    i = 0

    while i < len(df):

        row = df.iloc[i]

        # =========================
        # 出现买入信号
        # =========================

        if buy_signal(row):

            buy_date = row["date"]

            buy_price = row["close"]

            sell_date = None

            sell_price = None

            reason = None

            # =========================
            # 开始持有
            # =========================

            for j in range(1, hold_days + 1):

                # 防止越界
                if i + j >= len(df):

                    last_row = df.iloc[-1]

                    sell_date = last_row["date"]

                    sell_price = last_row["close"]

                    reason = "END_OF_DATA"

                    break

                current_row = df.iloc[i + j]

                current_high = current_row["high"]

                current_low = current_row["low"]

                # =========================
                # 止损
                # =========================

                stop_price = buy_price * (
                    1 + stop_loss
                )

                if current_low <= stop_price:

                    sell_date = current_row["date"]

                    sell_price = stop_price

                    reason = "STOP_LOSS"

                    break

                # =========================
                # 止盈
                # =========================

                take_profit_price = buy_price * (
                    1 + take_profit
                )

                if current_high >= take_profit_price:

                    sell_date = current_row["date"]

                    sell_price = take_profit_price

                    reason = "TAKE_PROFIT"

                    break

            # =========================
            # 到期卖出
            # =========================

            if sell_price is None:

                final_row = df.iloc[
                    min(
                        i + hold_days,
                        len(df) - 1
                    )
                ]

                sell_date = final_row["date"]

                sell_price = final_row["close"]

                reason = "TIME_EXIT"

            # =========================
            # 收益率
            # =========================

            ret = (
                sell_price - buy_price
            ) / buy_price * 100

            holding_days = (
                sell_date - buy_date
            ).days

            trades.append({

                "ETF": symbol,

                "Buy Date": buy_date.strftime(
                    "%Y-%m-%d"
                ),

                "Sell Date": sell_date.strftime(
                    "%Y-%m-%d"
                ),

                "Buy Price": round(
                    buy_price,
                    2
                ),

                "Sell Price": round(
                    sell_price,
                    2
                ),

                "Holding Days": holding_days,

                "Return (%)": round(
                    ret,
                    2
                ),

                "Exit Reason": reason

            })

            # =========================
            # 核心：
            # 持仓期间跳过
            # 不允许重复交易
            # =========================

            i += hold_days

        else:

            i += 1

    return trades

# =========================
# 主程序
# =========================

if __name__ == "__main__":

    data_dir = Path("data")

    indicator_files = data_dir.glob(
        "*_indicators.csv"
    )

    all_trades = []

    for filepath in indicator_files:

        try:

            trades = backtest_etf(
                filepath
            )

            all_trades.extend(
                trades
            )

        except Exception as e:

            print(
                f"{filepath.name} 回测失败: {e}"
            )

    # =========================
    # 输出结果
    # =========================

    if len(all_trades) == 0:

        print("没有交易")

    else:

        trade_df = pd.DataFrame(
            all_trades
        )

        print("\n")
        print("=" * 140)
        print("回测结果")
        print("=" * 140)

        print(
            trade_df.to_string(
                index=False
            )
        )

        print("=" * 140)

        # =========================
        # 策略统计
        # =========================

        avg_return = trade_df[
            "Return (%)"
        ].mean()

        win_rate = (
            trade_df["Return (%)"] > 0
        ).mean()

        print(
            f"\n平均收益率: {avg_return:.2f}%"
        )

        print(
            f"胜率: {win_rate*100:.2f}%"
        )