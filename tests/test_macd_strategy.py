import pandas as pd
from strategies.macd_strategy import generate_signals, MACD_MIN_BARS


def make_prices(values: list[float]) -> pd.Series:
    return pd.Series(values, name="close")


def test_insufficient_data_returns_hold():
    prices = make_prices([100.0] * 10)
    assert (generate_signals(prices) == "hold").all()


def test_min_bars_guard():
    prices = make_prices([100.0] * (MACD_MIN_BARS - 1))
    assert (generate_signals(prices) == "hold").all()


def test_output_length_matches_input():
    prices = make_prices([100.0] * 60)
    assert len(generate_signals(prices)) == 60


def test_output_values_valid():
    prices = make_prices([100.0] * 60)
    assert set(generate_signals(prices).unique()).issubset({"buy", "sell", "hold"})


def test_crossover_generates_buy():
    # 40 flat bars then sharply rising → MACD crosses above signal line after warmup
    prices = make_prices([100.0] * 40 + [100.0 + i * 3 for i in range(60)])
    assert "buy" in generate_signals(prices).values


def test_crossunder_generates_sell():
    # Rising then sharply falling → MACD crosses below signal line
    prices = make_prices([100.0 + i * 3 for i in range(50)] + [100.0 + 50 * 3 - i * 3 for i in range(50)])
    assert "sell" in generate_signals(prices).values


def test_flat_prices_produce_no_crossover():
    # Perfectly flat prices → MACD and signal converge to same value → no crossover
    prices = make_prices([100.0] * 60)
    signals = generate_signals(prices)
    assert "buy" not in signals.values
    assert "sell" not in signals.values
