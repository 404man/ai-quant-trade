import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app

client = TestClient(app)

MOCK_BULLISH = {"sentiment": "bullish", "confidence": 0.72}
MOCK_NEUTRAL = {"sentiment": "neutral", "confidence": 0.5}


def test_sentiment_returns_200():
    with patch("api.routes.sentiment.SentimentService") as MockSvc:
        MockSvc.return_value.get_sentiment.return_value = MOCK_BULLISH
        resp = client.get("/sentiment?symbol=AAPL")
    assert resp.status_code == 200


def test_sentiment_returns_valid_body():
    with patch("api.routes.sentiment.SentimentService") as MockSvc:
        MockSvc.return_value.get_sentiment.return_value = MOCK_BULLISH
        resp = client.get("/sentiment?symbol=AAPL")
    body = resp.json()
    assert body["sentiment"] == "bullish"
    assert body["confidence"] == 0.72


def test_sentiment_missing_symbol_returns_422():
    resp = client.get("/sentiment")
    assert resp.status_code == 422


def test_sentiment_fallback_still_200():
    # Even when service returns neutral fallback, route should return 200
    with patch("api.routes.sentiment.SentimentService") as MockSvc:
        MockSvc.return_value.get_sentiment.return_value = MOCK_NEUTRAL
        resp = client.get("/sentiment?symbol=AAPL")
    assert resp.status_code == 200
    assert resp.json()["sentiment"] == "neutral"


def test_sentiment_symbol_case_insensitive():
    with patch("api.routes.sentiment.SentimentService") as MockSvc:
        MockSvc.return_value.get_sentiment.return_value = MOCK_BULLISH
        resp_lower = client.get("/sentiment?symbol=aapl")
        resp_upper = client.get("/sentiment?symbol=AAPL")
    assert resp_lower.status_code == 200
    assert resp_upper.status_code == 200
