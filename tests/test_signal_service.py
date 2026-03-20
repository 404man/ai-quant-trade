import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from api.services.signal_service import SignalService


def make_prices(n: int = 100) -> list[dict]:
    import random
    import pandas as pd_inner
    random.seed(42)
    price = 100.0
    dates = pd_inner.date_range("2020-01-01", periods=n, freq="D")
    records = []
    for i in range(n):
        price = max(10.0, price + random.uniform(-2, 2))
        records.append({
            "date": dates[i].strftime("%Y-%m-%d"),
            "open": price - 0.1,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1000000,
        })
    return records


@pytest.fixture
def tmp_db(tmp_path):
    from db.schema import init_db
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def test_returns_required_keys(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "neutral", "confidence": 0.5}):
        result = svc.get_signal("AAPL", make_prices())
    assert {"action", "score", "size", "rsi_signal", "ma_signal",
            "sentiment", "sentiment_confidence"}.issubset(result.keys())


def test_action_is_valid_value(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "neutral", "confidence": 0.5}):
        result = svc.get_signal("AAPL", make_prices())
    assert result["action"] in ("buy", "sell", "hold")


def test_score_clamped_to_range(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "neutral", "confidence": 0.5}):
        result = svc.get_signal("AAPL", make_prices())
    assert -1.0 <= result["score"] <= 1.0


def test_size_within_bounds(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "bullish", "confidence": 0.9}):
        result = svc.get_signal("AAPL", make_prices())
    assert 0.0 <= result["size"] <= 0.10


def test_bullish_sentiment_boosts_buy_score(tmp_db):
    """Both strategies buy + bullish sentiment should score > both buy without sentiment boost."""
    svc = SignalService(db_path=tmp_db)
    # Force both signals to "buy" by patching strategy functions
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["buy"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "bullish", "confidence": 0.8}):
            result_bullish = svc.get_signal("AAPL", make_prices())
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result_neutral = svc.get_signal("AAPL", make_prices())
    assert result_bullish["score"] >= result_neutral["score"]


def test_buy_action_when_both_strategies_buy(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["buy"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", make_prices())
    assert result["action"] == "buy"


def test_hold_action_when_signals_conflict(tmp_db):
    """RSI buy + MA sell -> raw score 0 -> hold."""
    svc = SignalService(db_path=tmp_db)
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["sell"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", make_prices())
    assert result["action"] == "hold"


def test_insufficient_price_data_returns_hold(tmp_db):
    """Less than 30 bars -> all strategies return hold -> action is hold."""
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "bullish", "confidence": 0.9}):
        result = svc.get_signal("AAPL", make_prices(n=10))
    assert result["action"] == "hold"
    assert result["score"] == 0.0
