# Strategy Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MACD as a 3rd strategy vote, volume gate (thin volume halves score), and conviction bonus (2+ strategies agree → 1.3×) to improve signal Sharpe.

**Architecture:** New factor + strategy files follow the existing `strategies/factors/` + `strategies/` pattern. All aggregation changes are isolated to `SignalService`. No changes to RSI/MA strategies, backtest routes, or risk gate.

**Tech Stack:** Python 3.10, pandas, TA-Lib, pytest, SQLite

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `strategies/factors/macd_factor.py` | Create | MACD line + signal line via talib.MACD |
| `strategies/macd_strategy.py` | Create | MACD crossover → buy/sell/hold signals |
| `strategies/factors/volume_factor.py` | Create | Volume ratio vs 20-day rolling mean |
| `tests/test_macd_strategy.py` | Create | Tests for MACD strategy |
| `tests/test_volume_factor.py` | Create | Tests for volume factor |
| `api/services/signal_service.py` | Modify | Add MACD vote, volume gate, conviction bonus |
| `tests/test_signal_service.py` | Modify | Add tests for new aggregation logic |

---

### Task 1: MACD Factor + Strategy

**Files:**
- Create: `strategies/factors/macd_factor.py`
- Create: `strategies/macd_strategy.py`
- Test: `tests/test_macd_strategy.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_macd_strategy.py`:

```python
import pandas as pd
from strategies.macd_strategy import generate_signals, MACD_MIN_BARS


def make_prices(values: list[float]) -> pd.Series:
    return pd.Series(values, name="close")


def test_insufficient_data_returns_hold():
    prices = make_prices([100.0] * 10)
    assert (generate_signals(prices) == "hold").all()


def test_min_bars_guard():
    prices = make_prices([100.0] * (MACD_MIN_BARS - 1))
    assert (generate_signals(prices) == "hold").all()


def test_output_length_matches_input():
    prices = make_prices([100.0] * 60)
    assert len(generate_signals(prices)) == 60


def test_output_values_valid():
    prices = make_prices([100.0] * 60)
    assert set(generate_signals(prices).unique()).issubset({"buy", "sell", "hold"})


def test_crossover_generates_buy():
    # Flat then sharply rising → MACD crosses above signal line
    prices = make_prices([100.0] * 30 + [100.0 + i * 3 for i in range(30)])
    assert "buy" in generate_signals(prices).values


def test_crossunder_generates_sell():
    # Flat then sharply falling → MACD crosses below signal line
    prices = make_prices([100.0] * 30 + [100.0 - i * 3 for i in range(30)])
    assert "sell" in generate_signals(prices).values
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_macd_strategy.py -v
```
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 3: Create `strategies/factors/macd_factor.py`**

```python
import pandas as pd
import talib


def compute(
    prices: pd.Series,
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> tuple[pd.Series, pd.Series]:
    """
    Returns (macd_line, signal_line). First ~34 bars are NaN (talib warmup).
    """
    macd, signal, _ = talib.MACD(
        prices.values.astype("float64"),
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod,
    )
    return pd.Series(macd, index=prices.index), pd.Series(signal, index=prices.index)
```

- [ ] **Step 4: Create `strategies/macd_strategy.py`**

```python
import pandas as pd
from strategies.factors.macd_factor import compute as macd_compute

MACD_MIN_BARS = 35


def generate_signals(prices: pd.Series) -> pd.Series:
    """
    Buy: MACD line crosses above signal line.
    Sell: MACD line crosses below signal line.
    """
    signals = pd.Series("hold", index=prices.index)
    if len(prices) < MACD_MIN_BARS:
        return signals
    macd_line, signal_line = macd_compute(prices)
    crossover = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
    crossunder = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
    signals[crossover] = "buy"
    signals[crossunder] = "sell"
    return signals
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_macd_strategy.py -v
```
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add strategies/factors/macd_factor.py strategies/macd_strategy.py tests/test_macd_strategy.py
git commit -m "feat: MACD factor and strategy"
```

---

### Task 2: Volume Factor

**Files:**
- Create: `strategies/factors/volume_factor.py`
- Test: `tests/test_volume_factor.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_volume_factor.py`:

```python
import pandas as pd
from strategies.factors.volume_factor import compute


def test_ratio_length_matches_input():
    assert len(compute(pd.Series([1_000_000.0] * 30))) == 30


def test_ratio_is_one_for_flat_volume():
    result = compute(pd.Series([1_000_000.0] * 30))
    assert (result.iloc[20:].round(6) == 1.0).all()


def test_high_volume_ratio_above_one():
    result = compute(pd.Series([1_000_000.0] * 29 + [5_000_000.0]))
    assert result.iloc[-1] > 1.0


def test_low_volume_ratio_below_one():
    result = compute(pd.Series([1_000_000.0] * 29 + [100_000.0]))
    assert result.iloc[-1] < 1.0


def test_insufficient_history_fills_with_one():
    result = compute(pd.Series([1_000_000.0] * 5))
    assert not result.isna().any()
    assert (result == 1.0).all()


def test_zero_volume_does_not_raise():
    result = compute(pd.Series([0.0] * 30))
    assert not result.isna().any()
    assert (result == 1.0).all()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_volume_factor.py -v
```
Expected: ImportError

- [ ] **Step 3: Create `strategies/factors/volume_factor.py`**

```python
import pandas as pd


def compute(volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Returns volume / rolling_mean(volume, window).
    NaN (warmup) and zero-division positions filled with 1.0 (neutral).
    """
    rolling_mean = volume.rolling(window).mean()
    ratio = volume / rolling_mean
    ratio = ratio.replace([float("inf"), float("-inf")], 1.0)
    return ratio.fillna(1.0)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_volume_factor.py -v
```
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add strategies/factors/volume_factor.py tests/test_volume_factor.py
git commit -m "feat: volume ratio factor"
```

---

### Task 3: SignalService — MACD vote + volume gate + conviction bonus

**Files:**
- Modify: `api/services/signal_service.py`
- Modify: `tests/test_signal_service.py`

Read `api/services/signal_service.py` before editing (88 lines). The new version adds MACD as a 3rd vote, conviction bonus (2+ agree on non-zero direction → ×1.3), and volume gate (ratio < 1.0 → ×0.5). Existing sentiment boost and clamps are unchanged.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_signal_service.py` after the last test (line 118):

```python
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
    prices_normal = make_prices()  # volume=1_000_000 flat → ratio=1.0
    prices_low = [dict(r) for r in prices_normal]
    prices_low[-1]["volume"] = 1  # near-zero → ratio << 1.0
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
    """Flat volume → ratio=1.0 → no gate, score is unmodified."""
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
    # Use only 5 bars of volume data — insufficient for 20-bar rolling mean → NaN → filled to 1.0
    prices = make_prices()
    prices_short_vol = [dict(r) for r in prices]
    # Zero out volume for all but last 5 bars so rolling mean is NaN on last bar
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
    # NaN → 1.0 → no gate → score should be positive (not halved)
    assert result["score"] > 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_signal_service.py -v -k "macd_signal or volume_ratio or conviction or volume_gate"
```
Expected: AttributeError or ImportError (macd_signals not imported yet)

- [ ] **Step 3: Rewrite `api/services/signal_service.py`**

Replace the full file with:

```python
import pandas as pd
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals
from strategies.macd_strategy import generate_signals as macd_signals
from strategies.factors.volume_factor import compute as volume_compute
from api.services.sentiment_service import SentimentService
from db.schema import DEFAULT_DB_PATH

BUY_THRESHOLD = 0.3
SELL_THRESHOLD = -0.3
SENTIMENT_BOOST = 1.2
SENTIMENT_MIN_CONFIDENCE = 0.6
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
        self._sentiment_svc = SentimentService(db_path=db_path)

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
            "sentiment": "neutral",
            "sentiment_confidence": 0.5,
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

        sentiment_result = self._sentiment_svc.get_sentiment(symbol)
        sentiment = sentiment_result["sentiment"]
        sentiment_confidence = sentiment_result["confidence"]

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

        # Sentiment boost (clamps preserved)
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
            "macd_signal": macd_signal,
            "volume_ratio": round(volume_ratio, 4),
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,
        }
```

- [ ] **Step 4: Run all signal service tests**

```bash
python -m pytest tests/test_signal_service.py -v
```
Expected: All tests PASS (including 7 existing tests)

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -q
```
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add api/services/signal_service.py tests/test_signal_service.py
git commit -m "feat: signal service — MACD vote, volume gate, conviction bonus"
```
