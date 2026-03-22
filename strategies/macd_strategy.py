import pandas as pd
from strategies.factors.macd_factor import compute as macd_compute

MACD_MIN_BARS = 35


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    Buy: MACD line crosses above signal line.
    Sell: MACD line crosses below signal line.
    """
    signals = pd.Series("hold", index=prices.index)
    if len(prices) < MACD_MIN_BARS:
        return signals
    macd_line, signal_line = macd_compute(prices)
    prev_macd = macd_line.shift(1)
    prev_signal = signal_line.shift(1)
    crossover = (macd_line > signal_line) & (prev_macd.isna() | (prev_macd <= prev_signal))
    crossunder = (macd_line < signal_line) & (prev_macd.isna() | (prev_macd >= prev_signal))
    signals[crossover] = "buy"
    signals[crossunder] = "sell"
    return signals
