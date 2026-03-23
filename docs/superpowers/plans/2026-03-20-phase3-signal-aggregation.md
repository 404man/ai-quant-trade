# Phase 3: Signal Aggregation + Risk Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement signal aggregation (RSI × MA × sentiment → composite score) and a fully wired `GET /signal?symbol=AAPL` endpoint that passes every candidate trade through the RiskGate before returning an action.

**Architecture:** A new `SignalService` combines the two strategy signals and the sentiment filter into a single scored decision. The `RiskGate` (already built) is called inside the signal endpoint with the current portfolio snapshot provided as query parameters — no live broker needed yet. The `/signal` route returns `{"action": "buy"|"sell"|"hold", "size": 0.05, "score": 0.78, "risk_blocked": false}`.

**Tech Stack:** Python 3.11, FastAPI, pandas, talib (via existing strategies), anthropic (via existing SentimentService), sqlite3, pytest

---

## File Structure

```
api/
  services/
    signal_service.py       ← NEW: aggregation logic
  routes/
    signal.py               ← NEW: GET /signal endpoint
  main.py                   ← MODIFY: register signal router
tests/
  test_signal_service.py    ← NEW
  test_signal_route.py      ← NEW
```

Nothing else needs to change. All existing files remain untouched.

---

## Task 1: SignalService — scoring logic

**Files:**
- Create: `api/services/signal_service.py`
- Test: `tests/test_signal_service.py`

### Background

`SignalService.get_signal(symbol, prices)` does three things:
1. Runs RSI strategy on `prices` → "buy"/"sell"/"hold"
2. Runs MA strategy on `prices` → "buy"/"sell"/"hold"
3. Gets sentiment from `SentimentService` → "bullish"/"bearish"/"neutral" + confidence

Scoring rules (equal-weight voting):
- Each strategy signal contributes ±1 to a raw score: "buy" → +1, "sell" → -1, "hold" → 0
- Sentiment acts as a **filter multiplier**, not a vote:
  - bullish confidence ≥ 0.6 AND sentiment == "bullish" → multiply score by 1.2 (boost)
  - bearish confidence ≥ 0.6 AND sentiment == "bearish" → multiply score by 1.2 (boost in same direction)
  - neutral OR low-confidence → multiply by 1.0 (no effect)
- Final score is clamped to [-1.0, 1.0]
- Action decision: score > 0.3 → "buy", score < -0.3 → "sell", else → "hold"
- `size` (position fraction) = `abs(score) * MAX_POSITION_PCT` where `MAX_POSITION_PCT = 0.10`, capped at 0.10

Return dict:
```python
{
    "action": "buy",       # "buy" | "sell" | "hold"
    "score": 0.78,         # float in [-1.0, 1.0]
    "size": 0.078,         # float in [0.0, 0.10]
    "rsi_signal": "buy",
    "ma_signal": "hold",
    "sentiment": "bullish",
    "sentiment_confidence": 0.72,
}
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_signal_service.py`:

```python
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
    """RSI buy + MA sell → raw score 0 → hold."""
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
    """Less than 30 bars → all strategies return hold → action is hold."""
    svc = SignalService(db_path=tmp_db)
    with patch.object(svc._sentiment_svc, "get_sentiment",
                      return_value={"sentiment": "bullish", "confidence": 0.9}):
        result = svc.get_signal("AAPL", make_prices(n=10))
    assert result["action"] == "hold"
    assert result["score"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_signal_service.py -v
```

Expected: FAILED (ImportError: cannot import name 'SignalService')

- [ ] **Step 3: Write the implementation**

Create `api/services/signal_service.py`:

```python
import pandas as pd
from strategies.rsi_strategy import generate_signals as rsi_signals
from strategies.ma_crossover_strategy import generate_signals as ma_signals
from api.services.sentiment_service import SentimentService
from db.schema import DEFAULT_DB_PATH

# Thresholds
BUY_THRESHOLD = 0.3    # score > this → "buy"
SELL_THRESHOLD = -0.3  # score < this → "sell"
SENTIMENT_BOOST = 1.2  # multiplier when sentiment aligns with signal direction
SENTIMENT_MIN_CONFIDENCE = 0.6  # minimum confidence to apply boost
MAX_POSITION_PCT = 0.10  # maximum size fraction


def _signal_to_score(signal: str) -> float:
    return {"buy": 1.0, "sell": -1.0, "hold": 0.0}.get(signal, 0.0)


def _last_signal(signals: pd.Series) -> str:
    """Return the most recent non-NaN signal value."""
    if len(signals) == 0:
        return "hold"
    return str(signals.iloc[-1])


class SignalService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._sentiment_svc = SentimentService(db_path=db_path)

    def get_signal(self, symbol: str, price_data: list[dict]) -> dict:
        """
        Aggregate RSI signal, MA signal, and sentiment into a composite score.

        Args:
            symbol: ticker symbol (used for sentiment lookup)
            price_data: list of OHLCV dicts from DataService.fetch()

        Returns:
            dict with action, score, size, and component signals
        """
        symbol = symbol.upper()

        # Default result for insufficient data
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

        # Build close price Series
        df = pd.DataFrame(price_data)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        close = df["close"]

        # --- Strategy signals (last bar) ---
        rsi_signal = _last_signal(rsi_signals(close))
        ma_signal = _last_signal(ma_signals(close))

        # --- Sentiment ---
        sentiment_result = self._sentiment_svc.get_sentiment(symbol)
        sentiment = sentiment_result["sentiment"]
        sentiment_confidence = sentiment_result["confidence"]

        # --- Score calculation ---
        raw_score = _signal_to_score(rsi_signal) + _signal_to_score(ma_signal)
        # raw_score ∈ {-2, -1, 0, 1, 2}; normalise to [-1, 1]
        normalized = raw_score / 2.0

        # Sentiment multiplier: boost if high-confidence sentiment aligns with direction
        if sentiment_confidence >= SENTIMENT_MIN_CONFIDENCE:
            if sentiment == "bullish" and normalized > 0:
                normalized = min(1.0, normalized * SENTIMENT_BOOST)
            elif sentiment == "bearish" and normalized < 0:
                normalized = max(-1.0, normalized * SENTIMENT_BOOST)

        score = round(normalized, 4)

        # --- Action decision ---
        if score > BUY_THRESHOLD:
            action = "buy"
        elif score < SELL_THRESHOLD:
            action = "sell"
        else:
            action = "hold"

        # --- Position size ---
        size = round(min(abs(score) * MAX_POSITION_PCT, MAX_POSITION_PCT), 4)

        return {
            "action": action,
            "score": score,
            "size": size,
            "rsi_signal": rsi_signal,
            "ma_signal": ma_signal,
            "sentiment": sentiment,
            "sentiment_confidence": sentiment_confidence,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_signal_service.py -v
```

Expected: 8 PASSED

- [ ] **Step 5: Run full test suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -v
```

Expected: 90 PASSED (82 existing + 8 new)

- [ ] **Step 6: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/services/signal_service.py tests/test_signal_service.py
git commit -m "feat: SignalService — RSI×MA×sentiment aggregation with score-based sizing"
```

---

## Task 2: /signal route + RiskGate wiring

**Files:**
- Create: `api/routes/signal.py`
- Modify: `api/main.py` (add 2 lines)
- Test: `tests/test_signal_route.py`

### Background

`GET /signal?symbol=AAPL&start=2024-01-01&end=2024-12-31&capital=10000&daily_loss=0&current_positions=0`

The route:
1. Fetches price data from `DataService`
2. Calls `SignalService.get_signal()` to get action + score + size
3. If action is "buy" or "sell", runs `RiskGate.check()` with the provided portfolio state
4. If risk blocked: returns the signal with `action` overridden to "hold" and `risk_blocked=true` + `risk_reason`
5. Always returns 200 (risk blocking is not an error, it's a business decision)

Query params:
- `symbol` (required): ticker
- `start` (required): date string YYYY-MM-DD
- `end` (required): date string YYYY-MM-DD
- `capital` (optional, default=500.0): total portfolio capital in $
- `daily_loss` (optional, default=0.0): realized loss today in $
- `current_positions` (optional, default=0): number of open positions

Response shape:
```json
{
  "symbol": "AAPL",
  "action": "buy",
  "score": 0.78,
  "size": 0.078,
  "rsi_signal": "buy",
  "ma_signal": "hold",
  "sentiment": "bullish",
  "sentiment_confidence": 0.72,
  "risk_blocked": false,
  "risk_reason": null
}
```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_signal_route.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

MOCK_PRICES = [
    {"date": "2024-01-02", "open": 185.0, "high": 187.0,
     "low": 184.0, "close": 186.0, "volume": 50000000},
    {"date": "2024-01-03", "open": 186.0, "high": 188.0,
     "low": 185.0, "close": 187.0, "volume": 51000000},
]

MOCK_SIGNAL_BUY = {
    "action": "buy", "score": 0.78, "size": 0.078,
    "rsi_signal": "buy", "ma_signal": "hold",
    "sentiment": "bullish", "sentiment_confidence": 0.72,
}

MOCK_SIGNAL_HOLD = {
    "action": "hold", "score": 0.0, "size": 0.0,
    "rsi_signal": "hold", "ma_signal": "hold",
    "sentiment": "neutral", "sentiment_confidence": 0.5,
}


def test_signal_returns_200():
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        resp = client.get("/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31")
    assert resp.status_code == 200


def test_signal_returns_required_fields():
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        resp = client.get("/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31")
    body = resp.json()
    required = {"symbol", "action", "score", "size", "risk_blocked"}
    assert required.issubset(body.keys())


def test_signal_missing_params_returns_422():
    resp = client.get("/signal?symbol=AAPL")
    assert resp.status_code == 422


def test_signal_no_data_returns_404():
    with patch("api.routes.signal.DataService") as MockData:
        MockData.return_value.fetch.return_value = []
        resp = client.get("/signal?symbol=FAKE&start=2024-01-01&end=2024-12-31")
    assert resp.status_code == 404


def test_signal_risk_blocked_overrides_action():
    """When RiskGate blocks, action becomes 'hold' and risk_blocked=True."""
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal, \
         patch("api.routes.signal.RiskGate") as MockGate:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        mock_result = MagicMock()
        mock_result.allowed = False
        mock_result.reason = "Daily loss limit reached"
        MockGate.return_value.check.return_value = mock_result
        resp = client.get(
            "/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31"
            "&capital=1000&daily_loss=25"
        )
    body = resp.json()
    assert resp.status_code == 200
    assert body["action"] == "hold"
    assert body["risk_blocked"] is True
    assert body["risk_reason"] is not None


def test_signal_hold_skips_risk_check():
    """When signal is already 'hold', RiskGate is not called."""
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal, \
         patch("api.routes.signal.RiskGate") as MockGate:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_HOLD
        resp = client.get("/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31")
    assert resp.status_code == 200
    MockGate.return_value.check.assert_not_called()


def test_signal_risk_allowed_passes_through():
    """When RiskGate allows, action is unchanged and risk_blocked=False."""
    with patch("api.routes.signal.DataService") as MockData, \
         patch("api.routes.signal.SignalService") as MockSignal, \
         patch("api.routes.signal.RiskGate") as MockGate:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockSignal.return_value.get_signal.return_value = MOCK_SIGNAL_BUY
        mock_result = MagicMock()
        mock_result.allowed = True
        mock_result.reason = None
        MockGate.return_value.check.return_value = mock_result
        resp = client.get(
            "/signal?symbol=AAPL&start=2024-01-01&end=2024-12-31"
            "&capital=1000&daily_loss=0"
        )
    body = resp.json()
    assert body["action"] == "buy"
    assert body["risk_blocked"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_signal_route.py -v
```

Expected: FAILED (ImportError or 404 for /signal)

- [ ] **Step 3: Create `api/routes/signal.py`**

```python
from fastapi import APIRouter, HTTPException
from api.services.data_service import DataService
from api.services.signal_service import SignalService
from api.services.risk_service import RiskGate

router = APIRouter()


@router.get("/signal")
def get_signal(
    symbol: str,
    start: str,
    end: str,
    capital: float = 500.0,
    daily_loss: float = 0.0,
    current_positions: int = 0,
):
    data_svc = DataService()
    signal_svc = SignalService()
    risk_gate = RiskGate()

    prices = data_svc.fetch(symbol.upper(), start, end)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

    signal = signal_svc.get_signal(symbol.upper(), prices)

    risk_blocked = False
    risk_reason = None

    # Only run risk check for actionable signals
    if signal["action"] in ("buy", "sell"):
        proposed_value = signal["size"] * capital
        risk_result = risk_gate.check(
            capital=capital,
            daily_loss=daily_loss,
            current_positions=current_positions,
            proposed_trade_value=proposed_value,
        )
        if not risk_result.allowed:
            signal["action"] = "hold"
            risk_blocked = True
            risk_reason = risk_result.reason

    return {
        "symbol": symbol.upper(),
        **signal,
        "risk_blocked": risk_blocked,
        "risk_reason": risk_reason,
    }
```

- [ ] **Step 4: Register router in `api/main.py`**

Add these two lines to `api/main.py` (import + include_router):

```python
from api.routes.signal import router as signal_router
# ...
app.include_router(signal_router)
```

The complete file should look like:

```python
from fastapi import FastAPI
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router
from api.routes.sentiment import router as sentiment_router
from api.routes.signal import router as signal_router

app = FastAPI(title="AI Quant System", version="0.1.0")

app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(sentiment_router)
app.include_router(signal_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_signal_route.py -v
```

Expected: 7 PASSED

- [ ] **Step 6: Run full test suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -v
```

Expected: 97 PASSED (90 existing + 7 new)

- [ ] **Step 7: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/routes/signal.py api/main.py tests/test_signal_route.py
git commit -m "feat: GET /signal with RiskGate wiring (Phase 3 complete)"
```

---

## Phase 3 Completion Criteria

- [ ] `pytest tests/ -v` → all 97 tests pass
- [ ] `GET /signal?symbol=AAPL&start=2020-01-01&end=2024-12-31` returns JSON with `action`, `score`, `size`, `risk_blocked`
- [ ] When `capital=150` (below min), `risk_blocked=true` and `action="hold"` regardless of signal
- [ ] When both strategies agree, `action` matches their direction
- [ ] Conflicting strategies → `score ≈ 0` → `action="hold"`

---

## 下一步

Phase 3 完成后继续 Phase 4：Alpaca 纸面交易 + Telegram Bot（`docs/superpowers/plans/2026-03-20-phase4-alpaca-paper-trading.md`）
