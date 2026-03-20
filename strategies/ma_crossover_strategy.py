import pandas as pd
from strategies.factors.ma_factor import compute as ma_compute


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    MA(10/30) crossover signals.
    Entry: golden cross (fast crosses above slow).
    Exit: death cross (fast crosses below slow).
    """
    signals = pd.Series("hold", index=prices.index)
    if len(prices) < 30:
        return signals
    spread = ma_compute(prices)
    # Golden cross: spread goes from non-positive to positive
    golden_cross = (spread > 0) & (spread.shift(1) <= 0)
    # Death cross: spread goes from non-negative to negative
    death_cross = (spread < 0) & (spread.shift(1) >= 0)
    signals[golden_cross] = "buy"
    signals[death_cross] = "sell"
    return signals
