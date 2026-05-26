"""单 ETF 买入信号回测。

逻辑：发现买入信号后买入，最多持有 hold_days 天；
期间触发止损或止盈则提前卖出，否则到期卖出。
"""

import pandas as pd
from pathlib import Path

# =========================
# 买入信号
# =========================

def buy_signal(row):

    # 这是策略入口条件。多个 and 表示必须全部满足，才视为买入信号。
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

    # 从文件名中提取 ETF 代码。
    symbol = filepath.stem.replace(
        "_indicators",
        ""
    )

    # 读取指标数据。
    df = pd.read_csv(filepath)

    # 日期从字符串转为 datetime，便于计算持有天数。
    df["date"] = pd.to_datetime(
        df["date"]
    )

    # 保证时间顺序正确；drop=True 会丢掉旧索引。
    df = df.sort_values(
        "date"
    ).reset_index(drop=True)

    # trades 用来保存每一笔交易的结果。
    trades = []

    # i 是当前扫描到的行号；while 比 for 更灵活，因为买入后要跳过持仓期。
    i = 0

    while i < len(df):

        # 当前交易日的数据。
        row = df.iloc[i]

        # =========================
        # 出现买入信号
        # =========================

        if buy_signal(row):

            # 买入日期和买入价格以信号当天收盘价为准。
            buy_date = row["date"]

            buy_price = row["close"]

            # 先用 None 占位，后面根据卖出条件填入真实值。
            sell_date = None

            sell_price = None

            reason = None

            # =========================
            # 开始持有
            # =========================

            for j in range(1, hold_days + 1):

                # 防止越界：如果剩余数据不足 hold_days，就用最后一天卖出。
                if i + j >= len(df):

                    last_row = df.iloc[-1]

                    sell_date = last_row["date"]

                    sell_price = last_row["close"]

                    reason = "END_OF_DATA"

                    break

                current_row = df.iloc[i + j]

                # 日内最高价用于判断止盈，最低价用于判断止损。
                current_high = current_row["high"]

                current_low = current_row["low"]

                # =========================
                # 止损
                # =========================

                # stop_loss 是负数，例如 -0.05 表示从买入价下跌 5% 止损。
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

                # take_profit 是正数，例如 0.10 表示上涨 10% 止盈。
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

                # 没有触发止盈/止损时，到持有期最后一天按收盘价卖出。
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

            # 单笔收益率，乘以 100 后以百分数形式保存。
            ret = (
                sell_price - buy_price
            ) / buy_price * 100

            # datetime 相减得到 timedelta；.days 取相差天数。
            holding_days = (
                sell_date - buy_date
            ).days

            # 保存一笔完整交易。
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
            # 核心：持仓期间跳过，不允许在同一段持仓期内重复开仓。
            # =========================

            i += hold_days

        else:

            # 没有买入信号，则继续看下一天。
            i += 1

    return trades

# =========================
# 主程序
# =========================

if __name__ == "__main__":

    data_dir = Path("data")

    # 批量读取 data 目录下所有指标文件。
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

        # 把所有交易记录转成 DataFrame，方便统计。
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

        # 平均单笔收益率。
        avg_return = trade_df[
            "Return (%)"
        ].mean()

        # 胜率：收益率大于 0 的交易占比。布尔值 True/False 的均值等于 True 的比例。
        win_rate = (
            trade_df["Return (%)"] > 0
        ).mean()

        print(
            f"\n平均收益率: {avg_return:.2f}%"
        )

        print(
            f"胜率: {win_rate*100:.2f}%"
        )
