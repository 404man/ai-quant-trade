import pytest
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from db.schema import init_db
from api.services.sentiment_service import SentimentService, FALLBACK_RESPONSE


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def mock_claude_response(sentiment: str = "bullish", confidence: float = 0.72):
    """Returns a mock that makes SentimentService._call_claude return a fixed result."""
    mock = MagicMock()
    mock.return_value = {"sentiment": sentiment, "confidence": confidence}
    return mock


def test_returns_valid_structure(tmp_db):
    svc = SentimentService(db_path=tmp_db)
    with patch.object(svc, "_call_claude", mock_claude_response()):
        result = svc.get_sentiment("AAPL")
    assert "sentiment" in result
    assert "confidence" in result


def test_sentiment_is_valid_value(tmp_db):
    svc = SentimentService(db_path=tmp_db)
    with patch.object(svc, "_call_claude", mock_claude_response("bearish", 0.6)):
        result = svc.get_sentiment("AAPL")
    assert result["sentiment"] in ("bullish", "bearish", "neutral")


def test_cache_hit_skips_claude(tmp_db):
    svc = SentimentService(db_path=tmp_db)
    call_count = [0]

    def counting_claude(symbol):
        call_count[0] += 1
        return {"sentiment": "bullish", "confidence": 0.8}

    svc._call_claude = counting_claude
    svc.get_sentiment("AAPL")
    svc.get_sentiment("AAPL")  # second call — should use cache
    assert call_count[0] == 1


def test_cache_expires_after_ttl(tmp_db):
    svc = SentimentService(db_path=tmp_db)

    # Manually write an expired cache entry (2 hours ago)
    from db.schema import get_connection
    expired_at = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn = get_connection(tmp_db)
    conn.execute(
        "INSERT OR REPLACE INTO sentiment_cache (symbol, cached_at, sentiment, confidence) VALUES (?,?,?,?)",
        ("AAPL", expired_at, "bearish", 0.9)
    )
    conn.commit()
    conn.close()

    call_count = [0]
    def counting_claude(symbol):
        call_count[0] += 1
        return {"sentiment": "bullish", "confidence": 0.7}
    svc._call_claude = counting_claude

    svc.get_sentiment("AAPL")
    assert call_count[0] == 1  # cache was expired, Claude was called


def test_daily_limit_returns_fallback(tmp_db):
    svc = SentimentService(db_path=tmp_db)
    # Inject 50 calls for today into api_usage
    from db.schema import get_connection
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection(tmp_db)
    conn.execute(
        "INSERT OR REPLACE INTO api_usage (usage_date, api_name, call_count) VALUES (?, 'claude', 50)",
        (today,)
    )
    conn.commit()
    conn.close()

    result = svc.get_sentiment("AAPL")
    assert result["sentiment"] == "neutral"
    assert result["confidence"] == 0.5


def test_claude_failure_returns_fallback(tmp_db):
    svc = SentimentService(db_path=tmp_db)

    def failing_claude(symbol):
        raise Exception("API error")

    svc._call_claude = failing_claude
    result = svc.get_sentiment("AAPL")
    assert result["sentiment"] == "neutral"
    assert result["confidence"] == 0.5


def test_claude_failure_does_not_consume_usage_count(tmp_db):
    svc = SentimentService(db_path=tmp_db)

    def failing_claude(symbol):
        raise Exception("API error")

    svc._call_claude = failing_claude
    svc.get_sentiment("AAPL")

    from db.schema import get_connection
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_connection(tmp_db)
    row = conn.execute(
        "SELECT call_count FROM api_usage WHERE usage_date = ? AND api_name = 'claude'",
        (today,)
    ).fetchone()
    conn.close()
    count = row["call_count"] if row else 0
    assert count == 0


def test_symbol_normalized_to_upper(tmp_db):
    svc = SentimentService(db_path=tmp_db)
    call_count = [0]

    def counting_claude(symbol):
        call_count[0] += 1
        return {"sentiment": "bullish", "confidence": 0.8}

    svc._call_claude = counting_claude
    svc.get_sentiment("aapl")
    svc.get_sentiment("AAPL")  # should hit cache from first call
    assert call_count[0] == 1
