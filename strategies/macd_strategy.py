import pandas as pd
from strategies.factors.macd_factor import compute as macd_compute

MACD_MIN_BARS = 35  # slowperiod(26) + signalperiod(9) - 1


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
    crossover = prev_macd.notna() & (prev_macd <= prev_signal) & (macd_line > signal_line)
    crossunder = prev_macd.notna() & (prev_macd >= prev_signal) & (macd_line < signal_line)
    signals[crossover] = "buy"
    signals[crossunder] = "sell"
    return signals
