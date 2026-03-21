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
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="ord-abc", qty=1.0, price_estimate=253.0, reason=None
        )
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
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="ord-xyz", qty=1.0, price_estimate=253.0, reason=None
        )
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


def test_trade_default_gateway_uses_alpaca():
    """POST /trade without gateway field defaults to 'alpaca'."""
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="ord-default", qty=1.0, price_estimate=None, reason=None
        )
        resp = client.post("/trade", json=TRADE_BODY)  # no gateway field
    MockManager.route_order.assert_called_once()
    assert MockManager.route_order.call_args[0][0] == "alpaca"


def test_trade_with_binance_gateway():
    """POST /trade with gateway='binance' routes to Binance adapter."""
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="binance-ord-1", qty=0.01, price_estimate=50000.0, reason=None
        )
        body = {**TRADE_BODY, "gateway": "binance"}
        resp = client.post("/trade", json=body)
    assert resp.json()["status"] == "submitted"
    assert resp.json()["order_id"] == "binance-ord-1"
    MockManager.route_order.assert_called_once()
    assert MockManager.route_order.call_args[0][0] == "binance"


def test_trade_unknown_gateway_returns_400():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        MockManager.route_order.side_effect = KeyError("Unknown gateway: bogus")
        body = {**TRADE_BODY, "gateway": "bogus"}
        resp = client.post("/trade", json=body)
    assert resp.status_code == 400
