import pytest
import pandas as pd
import numpy as np
from strategies.rsi_strategy import generate_signals


def make_price_series(values: list[float]) -> pd.Series:
    return pd.Series(values, name="close")


def test_returns_series_with_signal_values():
    prices = make_price_series([100.0] * 30)
    signals = generate_signals(prices)
    assert isinstance(signals, pd.Series)
    assert set(signals.unique()).issubset({"buy", "sell", "hold"})


def test_oversold_generates_buy():
    # Steadily declining prices → RSI drops below 30
    prices = make_price_series([100 - i * 2 for i in range(30)])
    signals = generate_signals(prices)
    assert "buy" in signals.values


def test_overbought_generates_sell():
    # Steadily rising prices → RSI rises above 70
    prices = make_price_series([100 + i * 2 for i in range(30)])
    signals = generate_signals(prices)
    assert "sell" in signals.values


def test_insufficient_data_returns_hold():
    # RSI(14) needs at least 15 data points
    prices = make_price_series([100.0] * 10)
    signals = generate_signals(prices)
    assert (signals == "hold").all()


def test_output_length_matches_input():
    prices = make_price_series([100.0] * 50)
    signals = generate_signals(prices)
    assert len(signals) == len(prices)
