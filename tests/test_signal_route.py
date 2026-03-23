import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

MOCK_PRICES = [
    {"date": "2024-01-02", "open": 185.0, "high": 187.0,
     "low": 184.0, "close": 186.0, "volume": 50000000},
    {"date": "2024-01-03", "open": 186.0, "high": 188.0,
     "low": 185.0, "close": 187.0, "volume": 51000000},
]

MOCK_SIGNAL_BUY = {
    "action": "buy", "score": 0.78, "size": 0.078,
    "rsi_signal": "buy", "ma_signal": "hold",
    "macd_signal": "hold", "volume_ratio": 1.2,
}

MOCK_SIGNAL_HOLD = {
    "action": "hold", "score": 0.0, "size": 0.0,
    "rsi_signal": "hold", "ma_signal": "hold",
    "macd_signal": "hold", "volume_ratio": 1.0,
}


def test_signal_returns_200():
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        resp = client.get("/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31")
    assert resp.status_code == 200


def test_signal_returns_required_fields():
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        resp = client.get("/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31")
    body = resp.json()
    required = {"symbol", "action", "score", "size", "risk_blocked"}
    assert required.issubset(body.keys())


def test_signal_missing_params_returns_422():
    resp = client.get("/signal?symbol=AAPL")
    assert resp.status_code == 422


def test_signal_no_data_returns_404():
    with patch("api.routes.signal.DataService") as MockData:
        MockData.return_value.fetch.return_value = []
        resp = client.get("/signal?symbol=FAKE&start=2024-01-01&end=2024-12-31")
    assert resp.status_code == 404


def test_signal_risk_blocked_overrides_action():
    """When RiskGate blocks, action becomes 'hold' and risk_blocked=True."""
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal, \
         patch("api.routes.signal.RiskGate") as MockGate:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        mock_result = MagicMock()
        mock_result.allowed = False
        mock_result.reason = "Daily loss limit reached"
        MockGate.return_value.check.return_value = mock_result
        resp = client.get(
            "/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31"
            "&capital=1000&daily_loss=25"
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["action"] == "hold"
    assert body["risk_blocked"] is True
    assert body["risk_reason"] is not None


def test_signal_hold_skips_risk_check():
    """When signal is already 'hold', RiskGate is not called."""
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal, \
         patch("api.routes.signal.RiskGate") as MockGate:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_HOLD
        resp = client.get("/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31")
    assert resp.status_code == 200
    MockGate.return_value.check.assert_not_called()


def test_signal_risk_allowed_passes_through():
    """When RiskGate allows, action is unchanged and risk_blocked=False."""
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal, \
         patch("api.routes.signal.RiskGate") as MockGate:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        mock_result = MagicMock()
        mock_result.allowed = True
        mock_result.reason = None
        MockGate.return_value.check.return_value = mock_result
        resp = client.get(
            "/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31"
            "&capital=1000&daily_loss=0"
        )
    body = resp.json()
    assert body["action"] == "buy"
    assert body["risk_blocked"] is False
