import pandas as pd
import talib


def compute(prices: pd.Series, timeperiod: int = 14) -> pd.Series:
    """
    Compute RSI indicator values.
    Returns float Series of same length as prices.
    Values are NaN for the first (timeperiod) bars (talib warmup).
    """
    rsi = talib.RSI(prices.values.astype('float64'), timeperiod=timeperiod)
    return pd.Series(rsi, index=prices.index)
