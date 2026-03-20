import pytest
from api.services.backtest_service import BacktestService
import pandas as pd


def make_price_data(n: int = 200) -> list[dict]:
    import random
    import pandas as pd_inner
    random.seed(42)
    price = 100.0
    dates = pd_inner.date_range("2020-01-01", periods=n, freq="D")
    records = []
    for i in range(n):
        change = random.uniform(-2, 2)
        price = max(10.0, price + change)
        records.append({
            "date": dates[i].strftime("%Y-%m-%d"),
            "open": price - 0.1,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000000,
        })
    return records


def test_default_position_size_accepted():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert "sharpe_ratio" in result


def test_custom_position_size_accepted():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi", position_size_pct=0.05)
    assert "sharpe_ratio" in result


def test_position_size_does_not_change_trade_count():
    svc = BacktestService()
    result_10 = svc.run(make_price_data(), strategy="rsi", position_size_pct=0.10)
    result_05 = svc.run(make_price_data(), strategy="rsi", position_size_pct=0.05)
    # Same signals → same trade count regardless of sizing
    assert result_10["trade_count"] == result_05["trade_count"]


def test_bar_by_bar_mode_returns_valid_result():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi", mode="bar_by_bar")
    assert set(result.keys()) >= {"sharpe_ratio", "max_drawdown", "annual_return", "trade_count"}


def test_invalid_position_size_raises():
    svc = BacktestService()
    with pytest.raises(ValueError, match="position_size_pct"):
        svc.run(make_price_data(), strategy="rsi", position_size_pct=1.5)
