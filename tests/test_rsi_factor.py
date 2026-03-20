import pandas as pd
import numpy as np
from strategies.factors.rsi_factor import compute


def test_compute_returns_float_series():
    prices = pd.Series([float(100 + i % 5) for i in range(30)])
    result = compute(prices)
    assert isinstance(result, pd.Series)
    assert result.dtype == float or result.dtype == 'float64'


def test_compute_length_matches_input():
    prices = pd.Series([100.0] * 50)
    result = compute(prices)
    assert len(result) == len(prices)


def test_compute_oversold_below_30():
    # Declining prices → RSI should go below 30
    prices = pd.Series([100.0 - i * 2 for i in range(30)])
    result = compute(prices)
    # At least some values should be below 30 (after warmup)
    valid = result.dropna()
    assert (valid < 30).any()


def test_compute_overbought_above_70():
    # Rising prices → RSI should go above 70
    prices = pd.Series([100.0 + i * 2 for i in range(30)])
    result = compute(prices)
    valid = result.dropna()
    assert (valid > 70).any()


def test_compute_insufficient_data_has_nan():
    # Less than 15 bars → early values should be NaN (talib behavior)
    prices = pd.Series([100.0] * 10)
    result = compute(prices)
    assert result.isna().any()
