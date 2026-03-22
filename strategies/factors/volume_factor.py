import pandas as pd


def compute(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Returns volume / rolling_mean(volume, window).
    NaN (warmup) and zero-division positions filled with 1.0 (neutral).
    """
    rolling_mean = volume.rolling(window).mean()
    ratio = volume / rolling_mean
    ratio = ratio.replace([float("inf"), float("-inf")], 1.0)
    return ratio.fillna(1.0)
