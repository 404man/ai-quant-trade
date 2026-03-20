import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

TRADE_BODY = {
    "symbol": "AAPL",
    "action": "buy",
    "size": 0.05,
    "capital": 10000.0,
    "start": "2024-01-01",
    "end": "2024-12-31",
}

MOCK_PRICES = [
    {"date": "2024-12-30", "open": 252.0, "high": 255.0,
     "low": 250.0, "close": 253.0, "volume": 45000000},
]


def _make_risk_allowed():
    r = MagicMock()
    r.allowed = True
    r.reason = None
    return r


def _make_risk_blocked(reason="Daily loss limit"):
    r = MagicMock()
    r.allowed = False
    r.reason = reason
    return r


def test_trade_returns_200():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.submit_order.return_value = "ord-abc"
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code == 200


def test_trade_risk_blocked_returns_blocked_status():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_blocked("Capital too low")
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"
    assert "Capital too low" in resp.json()["reason"]


def test_trade_no_price_data_returns_error():
    with patch("api.routes.trade.DataService") as MockData:
        MockData.return_value.fetch.return_value = []
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"


def test_trade_confirmed_returns_submitted():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.submit_order.return_value = "ord-xyz"
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["order_id"] == "ord-xyz"


def test_trade_timeout_returns_cancelled():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade.send_cancellation_notice"), \
         patch("api.routes.trade._poll_confirmation", return_value="timeout"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["reason"] == "timeout"


def test_trade_user_rejected_returns_cancelled():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade.send_cancellation_notice"), \
         patch("api.routes.trade._poll_confirmation", return_value="cancelled"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["reason"] == "user_rejected"


def test_trade_missing_fields_returns_422():
    resp = client.post("/trade", json={"symbol": "AAPL"})
    assert resp.status_code == 422
