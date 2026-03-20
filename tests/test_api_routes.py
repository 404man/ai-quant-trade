import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

client = TestClient(app)

MOCK_PRICES = [
    {"date": "2024-01-02", "open": 185.0, "high": 187.0, "low": 184.0, "close": 186.0, "volume": 50000000},
    {"date": "2024-01-03", "open": 186.0, "high": 188.0, "low": 185.0, "close": 187.0, "volume": 51000000},
]

MOCK_BACKTEST = {
    "sharpe_ratio": 1.23,
    "max_drawdown": -0.15,
    "annual_return": 0.22,
    "trade_count": 42,
    "avg_holding_days": 5.0,
}


def test_data_price_returns_200():
    with patch("api.routes.data.DataService") as MockSvc:
        MockSvc.return_value.fetch.return_value = MOCK_PRICES
        resp = client.get("/data/price?symbol=AAPL&start=2024-01-01&end=2024-01-31")
    assert resp.status_code == 200


def test_data_price_returns_list():
    with patch("api.routes.data.DataService") as MockSvc:
        MockSvc.return_value.fetch.return_value = MOCK_PRICES
        resp = client.get("/data/price?symbol=AAPL&start=2024-01-01&end=2024-01-31")
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 2


def test_data_price_missing_params_returns_422():
    resp = client.get("/data/price?symbol=AAPL")
    assert resp.status_code == 422


def test_backtest_returns_200():
    with patch("api.routes.backtest.DataService") as MockData, \
         patch("api.routes.backtest.BacktestService") as MockBacktest:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockBacktest.return_value.run.return_value = MOCK_BACKTEST
        resp = client.get("/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2023-12-31")
    assert resp.status_code == 200


def test_backtest_returns_required_fields():
    with patch("api.routes.backtest.DataService") as MockData, \
         patch("api.routes.backtest.BacktestService") as MockBacktest:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockBacktest.return_value.run.return_value = MOCK_BACKTEST
        resp = client.get("/backtest?symbol=AAPL&strategy=rsi&start=2020-01-01&end=2023-12-31")
    body = resp.json()
    assert {"sharpe_ratio", "max_drawdown", "annual_return", "trade_count"}.issubset(body.keys())


def test_backtest_invalid_strategy_returns_400():
    with patch("api.routes.backtest.DataService") as MockData, \
         patch("api.routes.backtest.BacktestService") as MockBacktest:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockBacktest.return_value.run.side_effect = ValueError("Unknown strategy: invalid")
        resp = client.get("/backtest?symbol=AAPL&strategy=invalid&start=2020-01-01&end=2023-12-31")
    assert resp.status_code == 400


def test_backtest_no_data_returns_404():
    with patch("api.routes.backtest.DataService") as MockData:
        MockData.return_value.fetch.return_value = []
        resp = client.get("/backtest?symbol=FAKE&strategy=rsi&start=2020-01-01&end=2023-12-31")
    assert resp.status_code == 404


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
