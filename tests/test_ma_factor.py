import pandas as pd
import numpy as np
from strategies.factors.ma_factor import compute


def test_compute_returns_float_series():
    prices = pd.Series([float(100 + i % 5) for i in range(50)])
    result = compute(prices)
    assert isinstance(result, pd.Series)


def test_compute_length_matches_input():
    prices = pd.Series([100.0] * 50)
    result = compute(prices)
    assert len(result) == len(prices)


def test_positive_when_fast_above_slow():
    # Steadily rising prices → MA(10) > MA(30) at the end → spread positive
    prices = pd.Series([float(i) for i in range(50)])
    result = compute(prices)
    # Last value should be positive (fast MA > slow MA in uptrend)
    assert result.iloc[-1] > 0


def test_negative_when_fast_below_slow():
    # Steadily falling prices → MA(10) < MA(30) → spread negative
    prices = pd.Series([float(50 - i) for i in range(50)])
    result = compute(prices)
    assert result.iloc[-1] < 0


def test_first_29_bars_are_nan():
    # MA(30) needs 30 bars, so first 29 are NaN
    prices = pd.Series([100.0] * 50)
    result = compute(prices)
    assert result.iloc[:29].isna().all()
