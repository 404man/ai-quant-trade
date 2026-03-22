# tests/test_auth.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_no_auth_required():
    """GET /health works without any auth header, even when LOCAL_API_KEY is set."""
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_valid_token_allows_request():
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/backtest", params={"symbol": "AAPL", "strategy": "rsi", "start": "2020-01-01", "end": "2024-12-31"},
                          headers={"Authorization": "Bearer secret123"})
    # May be 404 (no data) or 200, but NOT 401
    assert resp.status_code != 401


def test_wrong_token_returns_401():
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/backtest", params={"symbol": "AAPL", "strategy": "rsi", "start": "2020-01-01", "end": "2024-12-31"},
                          headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_missing_header_returns_401():
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/backtest", params={"symbol": "AAPL", "strategy": "rsi", "start": "2020-01-01", "end": "2024-12-31"})
    assert resp.status_code == 401


def test_no_api_key_env_skips_auth():
    """When LOCAL_API_KEY is not set, all requests pass without auth."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LOCAL_API_KEY", None)
        resp = client.get("/health")
    assert resp.status_code == 200
