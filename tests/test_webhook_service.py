import os
import pytest
from unittest.mock import patch, MagicMock


def test_push_calls_httpx_post():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    with patch("api.services.webhook_service.httpx") as mock_httpx:
        svc.push("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})
    mock_httpx.post.assert_called_once()
    call_kwargs = mock_httpx.post.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer tok123"
    payload = call_kwargs[1]["json"]
    assert payload["name"] == "stock-signal"
    assert "AAPL" in payload["message"]


def test_push_silent_on_failure():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    with patch("api.services.webhook_service.httpx") as mock_httpx:
        mock_httpx.post.side_effect = Exception("connection refused")
        # Should not raise
        svc.push("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})


def test_push_skips_when_not_configured():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OPENCLAW_HOOK_URL", None)
        os.environ.pop("OPENCLAW_HOOK_TOKEN", None)
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    with patch("api.services.webhook_service.httpx") as mock_httpx:
        svc.push("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})
    mock_httpx.post.assert_not_called()


def test_format_signal_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})
    assert "AAPL" in msg
    assert "buy" in msg.lower() or "买" in msg


def test_format_risk_alert_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("risk_alert", {"symbol": "AAPL", "reason": "Daily loss limit reached"})
    assert "AAPL" in msg
    assert "Daily loss limit reached" in msg or "风控" in msg


def test_format_order_status_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("order_status", {"symbol": "AAPL", "action": "buy", "status": "submitted", "qty": 5, "price_estimate": 178.5, "order_id": "abc123"})
    assert "AAPL" in msg
    assert "5" in msg


def test_format_daily_summary_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("daily_summary", {
        "positions": [{"symbol": "AAPL", "qty": 5, "side": "long", "avg_entry_price": 178.5}],
        "daily_pnl": -12.5,
        "account_balance": 487.5,
        "date": "2026-03-22",
    })
    assert "AAPL" in msg
    assert "2026-03-22" in msg
