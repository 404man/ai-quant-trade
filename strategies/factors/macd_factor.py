import pandas as pd
import talib


def compute(
    prices: pd.Series,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> tuple[pd.Series, pd.Series]:
    """
    Returns (macd_line, signal_line). First ~34 bars are NaN (talib warmup).
    """
    macd, signal, _ = talib.MACD(
        prices.values.astype("float64"),
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod,
    )
    return pd.Series(macd, index=prices.index), pd.Series(signal, index=prices.index)
