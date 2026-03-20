import pytest
from api.services.backtest_service import BacktestService


def make_price_data(n: int = 200) -> list[dict]:
    """生成 n 天的合成价格数据"""
    import random
    import pandas as pd
    random.seed(42)
    price = 100.0
    dates = pd.date_range("2020-01-01", periods=n, freq="D")
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


def test_backtest_returns_required_keys():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert set(result.keys()) >= {"sharpe_ratio", "max_drawdown", "annual_return", "trade_count", "avg_holding_days"}


def test_backtest_sharpe_is_float():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert isinstance(result["sharpe_ratio"], float)


def test_backtest_max_drawdown_is_negative_or_zero():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert result["max_drawdown"] <= 0.0


def test_backtest_rsi_has_max_duration_exit():
    """RSI 策略：持仓超 10 日应强制出场（trade_count 应 > 0 且平均持仓 ≤ 10 天）"""
    svc = BacktestService()
    result = svc.run(make_price_data(n=200), strategy="rsi")
    # 有交易发生时，avg_holding_days 应 ≤ 10
    if result["trade_count"] > 0:
        assert result.get("avg_holding_days", 10) <= 10


def test_backtest_trade_count_is_non_negative():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="rsi")
    assert result["trade_count"] >= 0


def test_backtest_supports_ma_strategy():
    svc = BacktestService()
    result = svc.run(make_price_data(), strategy="ma")
    assert "sharpe_ratio" in result


def test_backtest_raises_on_unknown_strategy():
    svc = BacktestService()
    with pytest.raises(ValueError, match="Unknown strategy"):
        svc.run(make_price_data(), strategy="unknown")


def test_backtest_requires_minimum_data():
    svc = BacktestService()
    result = svc.run(make_price_data(n=10), strategy="rsi")
    # 数据不足时 trade_count 为 0
    assert result["trade_count"] == 0


def test_backtest_rsi_generates_trades_with_sufficient_data():
    svc = BacktestService()
    result = svc.run(make_price_data(n=200), strategy="rsi")
    # With 200 days of random-walk data, the RSI strategy should generate at least 1 trade
    assert result["trade_count"] > 0
