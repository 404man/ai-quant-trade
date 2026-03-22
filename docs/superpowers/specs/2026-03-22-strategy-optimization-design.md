# Strategy Optimization Design

**Date:** 2026-03-22

## Goal

Improve signal Sharpe by adding MACD as a 3rd strategy vote, gating signals on volume conviction, and applying a confluence bonus when 2+ strategies agree on a non-zero direction.

## Current State

- Two strategies: RSI mean-reversion (`rsi_strategy.py`), MA(10/30) crossover (`ma_crossover_strategy.py`)
- SignalService averages their scores equally, then applies a 1.2× sentiment boost when sentiment aligns
- No volume awareness, no multi-strategy confluence reward

## Architecture

Follows existing `strategies/factors/` + `strategies/` layering pattern. All new aggregation logic stays in `SignalService`.

### New Files

**`strategies/factors/macd_factor.py`**
- `compute(prices: pd.Series) -> tuple[pd.Series, pd.Series]`
- Returns `(macd_line, signal_line)` via `talib.MACD(fastperiod=12, slowperiod=26, signalperiod=9)`
- First ~34 bars are NaN (talib warmup)

**`strategies/macd_strategy.py`**
- `generate_signals(prices: pd.Series) -> pd.Series`
- Buy: MACD line crosses above signal line (previous bar ≤, current bar >)
- Sell: MACD line crosses below signal line (previous bar ≥, current bar <)
- Hold otherwise
- Requires minimum 35 bars (26 + 9 warmup); constant `MACD_MIN_BARS = 35` lives here (consistent with `RSI_MIN_BARS` in `rsi_strategy.py`)

**`strategies/factors/volume_factor.py`**
- `compute(volume: pd.Series, window: int = 20) -> pd.Series`
- Returns `volume / volume.rolling(window).mean()` — ratio Series
- Values > 1.0 mean above-average volume
- When rolling mean is NaN or zero (fewer than `window` bars), fill ratio with 1.0 (neutral — do not penalize insufficient data)

### Modified Files

**`api/services/signal_service.py`**

Data extraction (before scoring):
```python
df = pd.DataFrame(price_data)
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date").sort_index()
close = df["close"]
volume = df["volume"]  # extracted explicitly; KeyError if column missing is acceptable — callers must provide volume
```

Min-bars guard bumped from 30 → 35 (matches `MACD_MIN_BARS`).

Aggregation order of operations:
1. Compute RSI signal, MA signal, MACD signal (3 equal votes) — each returns 'buy'/'sell'/'hold'
2. Convert to scores: buy=+1, sell=-1, hold=0
3. Raw score = sum of three scores
4. Normalize: `normalized = raw_score / 3.0`
5. **Conviction bonus:** count strategies with non-zero score. If 2+ share the same sign (both positive or both negative), multiply by 1.3×, capped at ±1.0. Zero-score agreement does NOT trigger the bonus.
6. **Volume gate:** compute `volume_ratio = volume_factor.compute(volume).iloc[-1]`. If ratio < 1.0, multiply score by 0.5. If ratio is NaN (insufficient history), treat as 1.0 (no gate).
7. **Sentiment boost (existing):** if confidence ≥ 0.6 and sentiment aligns with score direction, multiply by 1.2×. Existing `min(1.0, ...)` / `max(-1.0, ...)` clamps still apply — final score is bounded to ±1.0.
8. Apply buy/sell/hold thresholds (unchanged: ±0.3)

New constants (in `signal_service.py`):
```python
CONVICTION_BONUS = 1.3
CONVICTION_MIN_COUNT = 2
VOLUME_LOW_MULTIPLIER = 0.5
VOLUME_RATIO_THRESHOLD = 1.0
```

Updated `empty` fallback dict (returned when `len(price_data) < 35`):
```python
empty = {
    "action": "hold",
    "score": 0.0,
    "size": 0.0,
    "rsi_signal": "hold",
    "ma_signal": "hold",
    "macd_signal": "hold",   # new
    "volume_ratio": 1.0,     # new
    "sentiment": "neutral",
    "sentiment_confidence": 0.5,
}
```

Response shape gains two new fields:
```python
{
    ...
    "macd_signal": "buy" | "sell" | "hold",
    "volume_ratio": float,  # last bar's volume / 20-day avg; 1.0 if insufficient history
}
```

## Testing

**`tests/test_macd_strategy.py`** (new)
- MACD crossover generates buy signal on last bar
- MACD crossunder generates sell signal on last bar
- Fewer than 35 bars returns all-hold
- Minimal warmup data (e.g., 10 bars) returns all-hold

**`tests/test_volume_factor.py`** (new)
- Normal case: returns ratio Series of same length as input
- Fewer than 20 bars: NaN positions filled with 1.0
- Zero volume (degenerate): does not raise, fills with 1.0

**`tests/test_signal_service.py`** (extend existing)
- Add `macd_signal` mock to existing test fixtures
- Test conviction bonus fires when 2+ strategies agree on non-zero direction
- Test conviction bonus does NOT fire when all strategies return hold (score=0)
- Test conviction bonus does NOT fire when strategies are split (e.g., buy + sell)
- Test volume gate halves score when `volume_ratio` < 1.0
- Test volume gate does NOT fire when `volume_ratio` ≥ 1.0
- Test NaN volume ratio treated as 1.0 (no gate applied)
- Test response includes `macd_signal` and `volume_ratio` fields
- Test `empty` fallback includes `macd_signal: "hold"` and `volume_ratio: 1.0`

## What Does NOT Change

- RSI and MA strategies — no modifications
- Sentiment service and its boost logic or clamp behavior
- Risk gate, thresholds (±0.3), MAX_POSITION_PCT
- Backtest service and backtest routes (they call strategies directly, not SignalService)
- API route shape (signal route just returns the dict from SignalService)
