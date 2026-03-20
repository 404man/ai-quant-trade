import pandas as pd
import talib


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    输入: 收盘价 Series（至少 15 个数据点才能计算 RSI(14)）
    输出: 同长度 Series，值为 "buy" / "sell" / "hold"
    规则: RSI < 30 → buy，RSI > 70 → sell，其余 → hold
    """
    signals = pd.Series("hold", index=prices.index)

    if len(prices) < 15:
        return signals

    rsi = talib.RSI(prices.values.astype('float64'), timeperiod=14)
    rsi_series = pd.Series(rsi, index=prices.index)

    signals[rsi_series < 30] = "buy"
    signals[rsi_series > 70] = "sell"

    return signals
