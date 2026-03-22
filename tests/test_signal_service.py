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


def test_returns_macd_signal_and_volume_ratio_keys(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "neutral", "confidence": 0.5}):
        result = svc.get_signal("AAPL", make_prices())
    assert "macd_signal" in result
    assert "volume_ratio" in result


def test_empty_fallback_includes_new_fields(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "neutral", "confidence": 0.5}):
        result = svc.get_signal("AAPL", make_prices(n=10))
    assert result["macd_signal"] == "hold"
    assert result["volume_ratio"] == 1.0
    assert result["action"] == "hold"


def test_conviction_bonus_fires_when_two_agree(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma, \
         patch("api.services.signal_service.macd_signals") as mock_macd:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["buy"] * 100)
        mock_macd.return_value = pd.Series(["hold"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", make_prices())
    # raw=(1+1+0)/3=0.667, with 1.3x bonus=0.867
    assert result["score"] > 0.65
    assert result["action"] == "buy"


def test_conviction_bonus_does_not_fire_for_all_hold(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma, \
         patch("api.services.signal_service.macd_signals") as mock_macd:
        mock_rsi.return_value = pd.Series(["hold"] * 100)
        mock_ma.return_value = pd.Series(["hold"] * 100)
        mock_macd.return_value = pd.Series(["hold"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", make_prices())
    assert result["score"] == 0.0
    assert result["action"] == "hold"


def test_conviction_bonus_does_not_fire_when_split(tmp_db):
    svc = SignalService(db_path=tmp_db)
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma, \
         patch("api.services.signal_service.macd_signals") as mock_macd:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["sell"] * 100)
        mock_macd.return_value = pd.Series(["hold"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", make_prices())
    assert result["action"] == "hold"


def test_volume_gate_halves_score_for_low_volume(tmp_db):
    svc = SignalService(db_path=tmp_db)
    prices_normal = make_prices()  # volume=1_000_000 flat -> ratio=1.0
    prices_low = [dict(r) for r in prices_normal]
    prices_low[-1]["volume"] = 1  # near-zero -> ratio << 1.0
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma, \
         patch("api.services.signal_service.macd_signals") as mock_macd:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["buy"] * 100)
        mock_macd.return_value = pd.Series(["buy"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result_normal = svc.get_signal("AAPL", prices_normal)
            result_low = svc.get_signal("AAPL", prices_low)
    assert result_low["score"] < result_normal["score"]


def test_volume_gate_does_not_fire_for_normal_volume(tmp_db):
    """Flat volume -> ratio=1.0 -> no gate, score is unmodified."""
    svc = SignalService(db_path=tmp_db)
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma, \
         patch("api.services.signal_service.macd_signals") as mock_macd:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["buy"] * 100)
        mock_macd.return_value = pd.Series(["buy"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", make_prices())
    assert result["volume_ratio"] >= 1.0
    assert result["score"] > 0.0


def test_nan_volume_ratio_treated_as_neutral(tmp_db):
    """When volume_factor returns NaN (filled to 1.0), no gate is applied."""
    svc = SignalService(db_path=tmp_db)
    prices = make_prices()
    prices_short_vol = [dict(r) for r in prices]
    for i in range(len(prices_short_vol) - 5):
        prices_short_vol[i]["volume"] = 0
    with patch("api.services.signal_service.rsi_signals") as mock_rsi, \
         patch("api.services.signal_service.ma_signals") as mock_ma, \
         patch("api.services.signal_service.macd_signals") as mock_macd:
        mock_rsi.return_value = pd.Series(["buy"] * 100)
        mock_ma.return_value = pd.Series(["buy"] * 100)
        mock_macd.return_value = pd.Series(["buy"] * 100)
        with patch.object(svc._sentiment_svc, "get_sentiment",
                          return_value={"sentiment": "neutral", "confidence": 0.5}):
            result = svc.get_signal("AAPL", prices_short_vol)
    # NaN -> 1.0 -> no gate -> score should be positive (not halved)
    assert result["score"] > 0.0
