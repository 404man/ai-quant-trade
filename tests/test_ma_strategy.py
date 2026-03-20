import pandas as pd
from strategies.ma_crossover_strategy import generate_signals


def test_returns_series_with_valid_values():
    prices = pd.Series([float(100 + i % 5) for i in range(50)])
    signals = generate_signals(prices)
    assert isinstance(signals, pd.Series)
    assert set(signals.unique()).issubset({"buy", "sell", "hold"})


def test_golden_cross_generates_buy():
    # First decline (death cross state), then rise (produces golden cross)
    down = [100 - i for i in range(30)]
    up = [70 + i for i in range(20)]
    prices = pd.Series(down + up)
    signals = generate_signals(prices)
    assert "buy" in signals.values


def test_death_cross_generates_sell():
    # Long uptrend first (golden cross stable), then sharp decline (produces death cross)
    # Need enough decline (40 points) to ensure MA(10) crosses below MA(30)
    up = [100 + i for i in range(40)]
    down = [140 - i * 2 for i in range(40)]
    prices = pd.Series(up + down)
    signals = generate_signals(prices)
    assert "sell" in signals.values


def test_insufficient_data_returns_hold():
    # MA(30) needs at least 30 data points
    prices = pd.Series([100.0] * 25)
    signals = generate_signals(prices)
    assert (signals == "hold").all()


def test_output_length_matches_input():
    prices = pd.Series([float(i) for i in range(60)])
    signals = generate_signals(prices)
    assert len(signals) == len(prices)
