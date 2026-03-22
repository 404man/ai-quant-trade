# Strategy Optimization Design

**Date:** 2026-03-22

## Goal

Improve signal Sharpe by adding MACD as a 3rd strategy vote, gating signals on volume conviction, and applying a confluence bonus when 2+ strategies agree on direction.

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
- Requires minimum 35 bars (26 + 9 warmup)

**`strategies/factors/volume_factor.py`**
- `compute(volume: pd.Series, window: int = 20) -> pd.Series`
- Returns `volume / volume.rolling(window).mean()` — ratio Series
- Values > 1.0 mean above-average volume

### Modified Files

**`api/services/signal_service.py`**

Aggregation order of operations:
1. Compute RSI signal, MA signal, MACD signal (3 equal votes)
2. Raw score = sum of signal scores (-1/0/+1 each)
3. Normalize: `score / 3.0`
4. Conviction bonus: if 2+ strategies agree on direction (same sign), multiply by 1.3×, capped at ±1.0
5. Volume gate: if last volume ratio < 1.0, multiply score by 0.5
6. Sentiment boost (existing): if confidence ≥ 0.6 and sentiment aligns, multiply by 1.2×
7. Apply buy/sell/hold thresholds (unchanged: ±0.3)

New constants:
```python
CONVICTION_BONUS = 1.3     # multiplier when 2+ strategies agree
CONVICTION_MIN_COUNT = 2   # strategies needed for bonus
VOLUME_LOW_MULTIPLIER = 0.5  # score penalty for thin volume
VOLUME_RATIO_THRESHOLD = 1.0  # below this = thin volume
MACD_MIN_BARS = 35
```

Response shape gains two new fields:
```python
{
    ...
    "macd_signal": "buy" | "sell" | "hold",
    "volume_ratio": float,  # last bar's volume / 20-day avg
}
```

Min bars guard bumped from 30 → 35.

## Testing

**`tests/test_macd_strategy.py`** (new)
- MACD crossover generates buy signal
- MACD crossunder generates sell signal
- Fewer than 35 bars returns all-hold
- Minimal warmup data returns all-hold

**`tests/test_signal_service.py`** (update existing or extend)
- Add `macd_signal` mock to existing test fixtures
- Test conviction bonus fires when 2+ strategies agree
- Test conviction bonus does NOT fire when strategies are mixed
- Test volume gate halves score when volume_ratio < 1.0
- Test volume gate does NOT fire when volume_ratio ≥ 1.0
- Test response includes `macd_signal` and `volume_ratio` fields

## What Does NOT Change

- RSI and MA strategies — no modifications
- Sentiment service and its boost logic
- Risk gate, thresholds (±0.3), MAX_POSITION_PCT
- Backtest service and backtest routes (they call strategies directly, not SignalService)
- API route shape (signal route just returns the dict from SignalService)
