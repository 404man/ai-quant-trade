import pandas as pd
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals
from strategies.macd_strategy import generate_signals as macd_signals
from strategies.factors.volume_factor import compute as volume_compute
from db.schema import DEFAULT_DB_PATH

BUY_THRESHOLD = 0.3
SELL_THRESHOLD = -0.3
MAX_POSITION_PCT = 0.10
CONVICTION_BONUS = 1.3
CONVICTION_MIN_COUNT = 2
VOLUME_LOW_MULTIPLIER = 0.5
VOLUME_RATIO_THRESHOLD = 1.0


def _signal_to_score(signal: str) -> float:
    return {"buy": 1.0, "sell": -1.0, "hold": 0.0}.get(signal, 0.0)


def _last_signal(signals: pd.Series) -> str:
    if len(signals) == 0:
        return "hold"
    return str(signals.iloc[-1])


class SignalService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def get_signal(self, symbol: str, price_data: list[dict]) -> dict:
        symbol = symbol.upper()

        empty = {
            "action": "hold",
            "score": 0.0,
            "size": 0.0,
            "rsi_signal": "hold",
            "ma_signal": "hold",
            "macd_signal": "hold",
            "volume_ratio": 1.0,
        }

        if len(price_data) < 35:
            return empty

        df = pd.DataFrame(price_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        close = df["close"]
        volume = df["volume"]

        rsi_signal = _last_signal(rsi_signals(close))
        ma_signal = _last_signal(ma_signals(close))
        macd_signal = _last_signal(macd_signals(close))

        scores = [_signal_to_score(rsi_signal), _signal_to_score(ma_signal), _signal_to_score(macd_signal)]
        raw_score = sum(scores)
        normalized = raw_score / 3.0

        # Conviction bonus: 2+ non-zero signals agree on same direction
        non_zero = [s for s in scores if s != 0.0]
        if len(non_zero) >= CONVICTION_MIN_COUNT and len(set(non_zero)) == 1:
            normalized = max(-1.0, min(1.0, normalized * CONVICTION_BONUS))

        # Volume gate: thin volume halves score
        volume_ratio = float(volume_compute(volume).iloc[-1])
        if volume_ratio < VOLUME_RATIO_THRESHOLD:
            normalized *= VOLUME_LOW_MULTIPLIER

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
            "macd_signal": macd_signal,
            "volume_ratio": round(volume_ratio, 4),
        }
