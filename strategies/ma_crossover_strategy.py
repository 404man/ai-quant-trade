import pandas as pd


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    输入: 收盘价 Series（至少 30 个数据点才能计算 MA(30)）
    输出: 同长度 Series，值为 "buy" / "sell" / "hold"
    规则: MA(10) 上穿 MA(30) → buy（金叉），MA(10) 下穿 MA(30) → sell（死叉）
    """
    signals = pd.Series("hold", index=prices.index)

    if len(prices) < 30:
        return signals

    ma_fast = prices.rolling(10).mean()
    ma_slow = prices.rolling(30).mean()

    # Golden cross: fast crosses above slow
    golden_cross = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
    # Death cross: fast crosses below slow
    death_cross = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))

    signals[golden_cross] = "buy"
    signals[death_cross] = "sell"

    return signals
