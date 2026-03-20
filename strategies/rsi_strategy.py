import pandas as pd
from strategies.factors.rsi_factor import compute as rsi_compute

RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_MIN_BARS = 15


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    RSI mean-reversion signals.
    Entry: RSI < 30 (oversold). Exit: RSI > 70 (overbought).
    """
    signals = pd.Series("hold", index=prices.index)
    if len(prices) < RSI_MIN_BARS:
        return signals
    rsi = rsi_compute(prices)
    signals[rsi < RSI_OVERSOLD] = "buy"
    signals[rsi > RSI_OVERBOUGHT] = "sell"
    return signals
