import pandas as pd
from strategies.factors.volume_factor import compute


def test_ratio_length_matches_input():
    assert len(compute(pd.Series([1_000_000.0] * 30))) == 30


def test_ratio_is_one_for_flat_volume():
    result = compute(pd.Series([1_000_000.0] * 30))
    assert (result.iloc[20:].round(6) == 1.0).all()


def test_high_volume_ratio_above_one():
    result = compute(pd.Series([1_000_000.0] * 29 + [5_000_000.0]))
    assert result.iloc[-1] > 1.0


def test_low_volume_ratio_below_one():
    result = compute(pd.Series([1_000_000.0] * 29 + [100_000.0]))
    assert result.iloc[-1] < 1.0


def test_insufficient_history_fills_with_one():
    result = compute(pd.Series([1_000_000.0] * 5))
    assert not result.isna().any()
    assert (result == 1.0).all()


def test_zero_volume_does_not_raise():
    result = compute(pd.Series([0.0] * 30))
    assert not result.isna().any()
    assert (result == 1.0).all()
