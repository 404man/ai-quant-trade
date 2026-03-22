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

Top: horizontal parameter bar (symbol / strategy / start / end / position size / run button). This form is shared — running it always updates the Overview tab result.

Below: shadcn `Tabs` with two tabs:

1. **概览 (Overview)** — metric cards with color coding + Sharpe badge + equity curve (standard height 250px)
2. **策略对比 (Compare)** — manual multi-run comparison table (has its own internal state, always visible)

> Note: Tab 2 (收益曲线) was removed — the chart is included in 概览 and adding a dedicated tab without meaningful difference would create confusion.

## Component Changes

### `web/components/strategies/BacktestForm.tsx` (modify)
- Add `macd` option to strategy dropdown (label: "MACD", value: `"macd"`)
- No other changes

### `web/components/strategies/BacktestResults.tsx` (modify)
- Color-code values:
  - `annual_return > 0` → `text-green-500`; `≤ 0` → `text-red-500`
  - `max_drawdown` always `text-red-500` (always negative)
  - `sharpe_ratio` → add inline badge after the number: `≥ 2.0` = "优秀" (green pill), `≥ 1.0` = "良好" (yellow pill), `< 1.0` = no badge
- No structural changes to the card grid

### `web/components/strategies/EquityCurve.tsx` (modify)
- Remove the drawdown shading feature entirely (the simulated curve has no real drawdown data; shading an arbitrary region would be misleading)
- Keep the existing "模拟" disclaimer label
- No other changes

### `web/components/strategies/CompareTab.tsx` (new)

**Types:**
```ts
interface CompareItem {
  id: string;           // uuid or index key
  symbol: string;
  strategy: string;     // must be one of: "rsi" | "ma" | "macd"
  start: string;
  end: string;
  positionSizePct: number;
  result?: BacktestResponse;
  loading: boolean;
}
```

**Initial state:** 2 default rows — `{ symbol: "AAPL", strategy: "rsi", start: "2020-01-01", end: "2024-12-31", positionSizePct: 0.1 }` and same with `strategy: "ma"`.

**UI:**
- List of rows, each with:
  - Symbol `<Input>`
  - Strategy `<Select>` with options RSI / MA 交叉 / MACD (mirroring `BacktestForm` dropdown, values: `"rsi"` / `"ma"` / `"macd"`)
  - Start `<Input type="date">`
  - End `<Input type="date">`
  - "重新运行" button (re-fetches that row even if result exists)
  - "删除" button (removes row; minimum 1 row enforced)
- "＋ 添加对比项" button appends a new row with defaults
- "运行全部" button triggers `fetchBacktest` for all rows that do not yet have a result; rows with existing results are skipped (use "重新运行" per-row to re-fetch)

**Results table** (shown when ≥ 1 row has a result):
- Columns: 组合 (symbol + strategy label), Sharpe, 年化收益, 最大回撤, 交易次数
- "Best" highlight per column (green background `bg-green-500/10`):
  - Sharpe → highest value
  - 年化收益 → highest value
  - 最大回撤 → highest value (least negative, i.e. closest to zero)
  - 交易次数 → highest value
- Overlay Recharts `LineChart` showing all result curves on the same axes (one line per completed row, using existing `buildCurve()` logic from EquityCurve)

**Empty state (no results yet):** show muted text "运行回测后显示对比结果" below the rows.

### `web/app/strategies/page.tsx` (modify)
- `BacktestForm` stays above the tabs (shared)
- Wrap results in shadcn `Tabs` / `TabsList` / `TabsTrigger` / `TabsContent`
- Tab 1 (概览): when `result` is null, show muted placeholder "运行回测后显示结果"; when result exists, show `<BacktestResults>` then `<EquityCurve>`
- Tab 2 (策略对比): always rendered, `<CompareTab>` manages its own state
- Default active tab: 概览

## What Does NOT Change

- `web/lib/api.ts` — no changes
- `web/lib/types.ts` — no changes
- Backend routes — no changes
- Existing backtest logic and data fetching in `strategies/page.tsx`

## Verification

Manual checks after implementation:
- All tabs render without errors
- Metric card colors correct (green annual return when positive, red drawdown)
- Sharpe badge appears at correct thresholds (≥2 优秀, ≥1 良好)
- CompareTab: add/delete rows work; strategy Select has RSI/MA/MACD options
- "运行全部" skips rows with existing results; "重新运行" re-fetches individual row
- Table highlights best value per column with correct "best" direction
- Build passes: `cd web && npm run build`
