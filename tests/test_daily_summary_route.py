# tests/test_daily_summary_route.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)


def test_daily_summary_triggers_webhook():
    mock_trade_svc = MagicMock()
    mock_trade_svc.get_positions.return_value = [
        {"symbol": "AAPL", "qty": 5, "avg_entry_price": 178.5, "side": "long"}
    ]
    mock_trade_svc.get_daily_loss.return_value = 12.5
    mock_trade_svc._get_client.side_effect = Exception("no creds")

    with patch("api.routes.daily_summary.TradeService", return_value=mock_trade_svc), \
         patch("api.routes.daily_summary.WebhookService") as MockWH:
        mock_wh_instance = MockWH.return_value
        resp = client.post("/daily-summary")

    assert resp.status_code == 200
    assert resp.json() == {"status": "sent"}
    mock_wh_instance.push.assert_called_once()
    call_args = mock_wh_instance.push.call_args
    assert call_args[0][0] == "daily_summary"
    data = call_args[0][1]
    assert data["daily_pnl"] == -12.5
    assert data["account_balance"] is None  # Alpaca unavailable
    assert len(data["positions"]) == 1


def test_daily_summary_with_balance():
    mock_trade_svc = MagicMock()
    mock_trade_svc.get_positions.return_value = []
    mock_trade_svc.get_daily_loss.return_value = 0.0
    mock_account = MagicMock()
    mock_account.equity = "500.00"
    mock_trade_svc._get_client.return_value.get_account.return_value = mock_account

    with patch("api.routes.daily_summary.TradeService", return_value=mock_trade_svc), \
         patch("api.routes.daily_summary.WebhookService") as MockWH:
        mock_wh_instance = MockWH.return_value
        resp = client.post("/daily-summary")

    assert resp.status_code == 200
    data = mock_wh_instance.push.call_args[0][1]
    assert data["account_balance"] == 500.0
