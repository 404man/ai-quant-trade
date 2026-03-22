# 策略库页面重设计

**Date:** 2026-03-22

## Goal

Rebuild the strategies page from a flat form+results layout into a tabbed interface with richer metric display and multi-strategy comparison.

## Current State

- `web/app/strategies/page.tsx` — flat layout: form on top, metric cards, equity curve
- `web/components/strategies/BacktestForm.tsx` — horizontal form, no MACD option
- `web/components/strategies/BacktestResults.tsx` — 5 metric cards, no color coding
- `web/components/strategies/EquityCurve.tsx` — Recharts line chart, simulated curve

## Layout

Top: horizontal parameter bar (symbol / strategy / start / end / position size / run button).

Below: shadcn `Tabs` with three tabs:

1. **概览 (Overview)** — metric cards with color coding + Sharpe badge
2. **收益曲线 (Equity Curve)** — chart with max drawdown shading
3. **策略对比 (Compare)** — manual multi-run comparison table

## Component Changes

### `web/components/strategies/BacktestForm.tsx` (modify)
- Add `macd` option to strategy dropdown (label: "MACD", value: `"macd"`)
- No other changes

### `web/components/strategies/BacktestResults.tsx` (modify)
- Color-code values:
  - `annual_return > 0` → green (`text-green-500`); `≤ 0` → red
  - `max_drawdown` always red (always negative)
  - `sharpe_ratio` → add badge: `≥ 2.0` = "优秀" (green), `≥ 1.0` = "良好" (yellow), `< 1.0` = no badge
- No structural changes to the card grid

### `web/components/strategies/EquityCurve.tsx` (modify)
- Add max drawdown shading: a `ReferenceArea` (Recharts) covering the approximate drawdown region
- Drawdown region estimated from `result.max_drawdown` and `result.annual_return` — shade the worst 20% of the time range as a light red area
- Keep existing simulated curve logic

### `web/components/strategies/CompareTab.tsx` (new)
- State: `items: CompareItem[]` where `CompareItem = { symbol, strategy, start, end, positionSizePct, result?: BacktestResponse, loading: boolean }`
- UI:
  - List of rows, each with symbol / strategy / date inputs + delete button
  - "＋ 添加对比项" button appends a new row with defaults
  - "运行全部" button triggers `fetchBacktest` for all items without results
  - Results table: columns = Strategy, Sharpe, 年化收益, 最大回撤, 交易次数; best value per column highlighted with green background
  - Overlay line chart (Recharts) showing all result curves on same axes
- Requires at least 1 item; starts with 2 default rows (RSI + MA for AAPL 2020-2024)

### `web/app/strategies/page.tsx` (modify)
- Wrap results area in shadcn `Tabs` / `TabsList` / `TabsTrigger` / `TabsContent`
- `BacktestForm` remains above tabs, shared across all tabs
- Tab 1 (概览): `<BacktestResults>` + `<EquityCurve>` (shown only when `result` exists)
- Tab 2 (收益曲线): `<EquityCurve>` full-width (shown only when `result` exists)
- Tab 3 (策略对比): `<CompareTab>` always shown (has its own internal state)
- Default active tab: 概览

## What Does NOT Change

- `web/lib/api.ts` — no changes
- `web/lib/types.ts` — no changes
- Backend routes — no changes
- Existing backtest logic and data fetching in `strategies/page.tsx`

## Testing

This is a pure frontend change. Manual verification:
- All three tabs render without errors
- Metric card colors correct (green annual return, red drawdown)
- Sharpe badge appears at correct thresholds
- CompareTab: add/delete rows, run all, table highlights best column values
- Build passes: `cd web && npm run build`
