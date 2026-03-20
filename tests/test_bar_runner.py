import pandas as pd
import numpy as np
from strategies.bar_runner import run_bar_by_bar
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals


def make_prices(n: int = 100) -> pd.Series:
    import random
    random.seed(42)
    price = 100.0
    prices = []
    for _ in range(n):
        price = max(10.0, price + random.uniform(-2, 2))
        prices.append(price)
    return pd.Series(prices)


def test_output_length_matches_input():
    prices = make_prices(100)
    result = run_bar_by_bar(prices, rsi_signals)
    assert len(result) == len(prices)


def test_output_values_are_valid_signals():
    prices = make_prices(100)
    result = run_bar_by_bar(prices, rsi_signals)
    assert set(result.unique()).issubset({"buy", "sell", "hold"})


def test_short_input_returns_hold():
    prices = make_prices(10)
    result = run_bar_by_bar(prices, rsi_signals, lookback=50)
    assert (result == "hold").all()


def test_works_with_ma_strategy():
    prices = make_prices(100)
    result = run_bar_by_bar(prices, ma_signals, lookback=50)
    assert isinstance(result, pd.Series)
    assert set(result.unique()).issubset({"buy", "sell", "hold"})


def test_no_lookahead():
    """
    Critical test: signal at bar i must not depend on data at bar i+1.
    Inject an extreme spike at bar i+1 and verify bar i's signal is unchanged.
    """
    prices = make_prices(80)

    # Get signal at bar 40 using original prices
    result_original = run_bar_by_bar(prices, rsi_signals, lookback=50)
    signal_at_40 = result_original.iloc[40]

    # Inject extreme spike at bar 41 (future relative to bar 40)
    prices_modified = prices.copy()
    prices_modified.iloc[41] = 999999.0

    result_modified = run_bar_by_bar(prices_modified, rsi_signals, lookback=50)
    signal_at_40_modified = result_modified.iloc[40]

    # Signal at bar 40 must be identical — bar 41 data should not affect it
    assert signal_at_40 == signal_at_40_modified
