import pandas as pd
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals
from api.services.sentiment_service import SentimentService
from db.schema import DEFAULT_DB_PATH

# Thresholds
BUY_THRESHOLD = 0.3    # score > this -> "buy"
SELL_THRESHOLD = -0.3  # score < this -> "sell"
SENTIMENT_BOOST = 1.2  # multiplier when sentiment aligns with signal direction
SENTIMENT_MIN_CONFIDENCE = 0.6  # minimum confidence to apply boost
MAX_POSITION_PCT = 0.10  # maximum size fraction


def _signal_to_score(signal: str) -> float:
    return {"buy": 1.0, "sell": -1.0, "hold": 0.0}.get(signal, 0.0)


def _last_signal(signals: pd.Series) -> str:
    """Return the last signal from the series (strategies always return buy/sell/hold)."""
    if len(signals) == 0:
        return "hold"
    return str(signals.iloc[-1])


class SignalService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._sentiment_svc = SentimentService(db_path=db_path)

    def get_signal(self, symbol: str, price_data: list[dict]) -> dict:
        symbol = symbol.upper()

        empty = {
            "action": "hold",
            "score": 0.0,
            "size": 0.0,
            "rsi_signal": "hold",
            "ma_signal": "hold",
            "sentiment": "neutral",
            "sentiment_confidence": 0.5,
        }

        if len(price_data) < 30:
            return empty

        df = pd.DataFrame(price_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        close = df["close"]

        rsi_signal = _last_signal(rsi_signals(close))
        ma_signal = _last_signal(ma_signals(close))

        sentiment_result = self._sentiment_svc.get_sentiment(symbol)
        sentiment = sentiment_result["sentiment"]
        sentiment_confidence = sentiment_result["confidence"]

        raw_score = _signal_to_score(rsi_signal) + _signal_to_score(ma_signal)
        normalized = raw_score / 2.0

        if sentiment_confidence >= SENTIMENT_MIN_CONFIDENCE:
            if sentiment == "bullish" and normalized > 0:
                normalized = min(1.0, normalized * SENTIMENT_BOOST)
            elif sentiment == "bearish" and normalized < 0:
                normalized = max(-1.0, normalized * SENTIMENT_BOOST)

        score = round(normalized, 4)

        if score > BUY_THRESHOLD:
            action = "buy"
        elif score < SELL_THRESHOLD:
            action = "sell"
        else:
            action = "hold"

        size = round(min(abs(score) * MAX_POSITION_PCT, MAX_POSITION_PCT), 4) if action != "hold" else 0.0

        return {
            "action": action,
            "score": score,
            "size": size,
            "rsi_signal": rsi_signal,
            "ma_signal": ma_signal,
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,
        }
