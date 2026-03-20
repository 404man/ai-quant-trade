from typing import Callable
import pandas as pd


def run_bar_by_bar(
    prices: pd.Series,
    signal_fn: Callable[[pd.Series], pd.Series],
    lookback: int = 50,
) -> pd.Series:
    """
    Feed prices one bar at a time to signal_fn to prevent look-ahead bias.

    For bar i, calls signal_fn with prices[max(0, i-lookback+1) : i+1].
    Takes only the LAST element of the returned signal Series as the signal for bar i.

    Both existing strategies handle short inputs gracefully (return "hold" when
    fewer than min_bars provided), so lookback can safely be smaller than the
    strategy's minimum.

    Performance: O(n * lookback) — suitable for backtesting, not live tick-by-tick.
    """
    signals = pd.Series("hold", index=prices.index)

    for i in range(len(prices)):
        start = max(0, i - lookback + 1)
        window = prices.iloc[start : i + 1]
        window_signals = signal_fn(window)
        signals.iloc[i] = window_signals.iloc[-1]

    return signals
