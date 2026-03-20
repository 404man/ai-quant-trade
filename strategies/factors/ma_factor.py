import pandas as pd


def compute(prices: pd.Series, fast: int = 10, slow: int = 30) -> pd.Series:
    """
    Compute the spread between fast and slow moving averages: MA(fast) - MA(slow).
    Positive values mean fast MA is above slow MA (uptrend).
    Negative values mean fast MA is below slow MA (downtrend).
    First (slow - 1) values are NaN.
    """
    ma_fast = prices.rolling(fast).mean()
    ma_slow = prices.rolling(slow).mean()
    return ma_fast - ma_slow
