# Strategies UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the strategies page with a tabbed layout (概览 / 策略对比), color-coded metrics, Sharpe badge, and a CompareTab for multi-strategy comparison.

**Architecture:** Pure frontend changes. `BacktestForm` gets MACD option. `BacktestResults` gets color coding + badge. New `CompareTab` component manages its own compare state. `StrategiesPage` wraps results in shadcn Tabs. No backend changes.

**Tech Stack:** Next.js 14 App Router, TypeScript, Tailwind CSS, shadcn/ui (Tabs, Select, Card), Recharts

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `web/components/strategies/BacktestForm.tsx` | Modify | Add MACD to strategy dropdown |
| `web/components/strategies/BacktestResults.tsx` | Modify | Color-code metrics, add Sharpe badge |
| `web/components/strategies/EquityCurve.tsx` | Modify | Remove drawdown shading (no-op — already not in code) |
| `web/components/strategies/CompareTab.tsx` | Create | Multi-strategy compare UI |
| `web/app/strategies/page.tsx` | Modify | Wrap results in shadcn Tabs |

---

### Task 1: BacktestForm — add MACD option

**Files:**
- Modify: `web/components/strategies/BacktestForm.tsx:48-56`

Current strategy Select has two items: RSI and MA 交叉. Add MACD as a third.

- [ ] **Step 1: Edit `web/components/strategies/BacktestForm.tsx`**

Find the `<SelectContent>` block (around line 52) and add the MACD item:

```tsx
<SelectContent>
  <SelectItem value="rsi">RSI</SelectItem>
  <SelectItem value="ma">MA 交叉</SelectItem>
  <SelectItem value="macd">MACD</SelectItem>
</SelectContent>
```

- [ ] **Step 2: Verify build passes**

```bash
cd web && npm run build
```
Expected: Build succeeds, no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add web/components/strategies/BacktestForm.tsx
git commit -m "feat: add MACD option to backtest form strategy dropdown"
```

---

### Task 2: BacktestResults — color coding + Sharpe badge

**Files:**
- Modify: `web/components/strategies/BacktestResults.tsx`

Current file (38 lines): renders 5 metric cards with no color. New version adds color to annual_return and max_drawdown, and a badge after the Sharpe number.

- [ ] **Step 1: Rewrite `web/components/strategies/BacktestResults.tsx`**

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BacktestResponse } from "@/lib/types";

type MetricKey = "sharpe_ratio" | "max_drawdown" | "annual_return" | "trade_count" | "avg_holding_days";

function fmt(value: number, key: MetricKey): string {
  if (key === "max_drawdown" || key === "annual_return") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (key === "sharpe_ratio") return value.toFixed(4);
  if (key === "avg_holding_days") return `${value.toFixed(1)} 天`;
  return String(value);
}

function valueColor(value: number, key: MetricKey): string {
  if (key === "annual_return") return value > 0 ? "text-green-500" : "text-red-500";
  if (key === "max_drawdown") return "text-red-500";
  return "";
}

function SharpeBadge({ value }: { value: number }) {
  if (value >= 2.0) {
    return <span className="ml-2 text-xs font-medium px-1.5 py-0.5 rounded bg-green-100 text-green-700">优秀</span>;
  }
  if (value >= 1.0) {
    return <span className="ml-2 text-xs font-medium px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700">良好</span>;
  }
  return null;
}

export function BacktestResults({ result }: { result: BacktestResponse }) {
  const metrics = [
    { label: "Sharpe Ratio", key: "sharpe_ratio" },
    { label: "最大回撤", key: "max_drawdown" },
    { label: "年化收益", key: "annual_return" },
    { label: "交易次数", key: "trade_count" },
    { label: "平均持仓", key: "avg_holding_days" },
  ] as const;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {metrics.map(({ label, key }) => (
        <Card key={key}>
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-muted-foreground font-normal">{label}</CardTitle>
          </CardHeader>
          <CardContent className="pb-4 px-4">
            <p className={`text-xl font-semibold flex items-center ${valueColor(result[key], key)}`}>
              {fmt(result[key], key)}
              {key === "sharpe_ratio" && <SharpeBadge value={result[key]} />}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify build passes**

```bash
cd web && npm run build
```
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add web/components/strategies/BacktestResults.tsx
git commit -m "feat: color-code metrics and add Sharpe badge in BacktestResults"
```

---

### Task 3: CompareTab component

**Files:**
- Create: `web/components/strategies/CompareTab.tsx`

This is the most complex new component. It manages a list of compare items, each with its own backtest params and result. Users can add/delete rows, run all, re-run individual rows. Results shown in a table (best value highlighted) and an overlay line chart.

- [ ] **Step 1: Create `web/components/strategies/CompareTab.tsx`**

```tsx
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { fetchBacktest } from "@/lib/api";
import type { BacktestResponse } from "@/lib/types";
import { useToast } from "@/components/ui/use-toast";

const STRATEGY_LABELS: Record<string, string> = {
  rsi: "RSI",
  ma: "MA 交叉",
  macd: "MACD",
};

interface CompareItem {
  id: string;
  symbol: string;
  strategy: string;
  start: string;
  end: string;
  positionSizePct: number;
  result?: BacktestResponse;
  loading: boolean;
}

const DEFAULT_ITEMS: CompareItem[] = [
  { id: "1", symbol: "AAPL", strategy: "rsi", start: "2020-01-01", end: "2024-12-31", positionSizePct: 0.1, loading: false },
  { id: "2", symbol: "AAPL", strategy: "ma", start: "2020-01-01", end: "2024-12-31", positionSizePct: 0.1, loading: false },
];

function buildCurve(result: BacktestResponse): { date: string; value: number }[] {
  const start = new Date(result.start);
  const end = new Date(result.end);
  const days = Math.ceil((end.getTime() - start.getTime()) / 86_400_000);
  const dailyRate = Math.pow(1 + result.annual_return, 1 / 252) - 1;
  const points: { date: string; value: number }[] = [];
  let value = 1.0;
  for (let i = 0; i <= days; i += Math.max(1, Math.floor(days / 60))) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    points.push({ date: d.toISOString().slice(0, 10), value: parseFloat(value.toFixed(4)) });
    value *= 1 + dailyRate;
  }
  return points;
}

const COLORS = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed"];

function bestIndices(items: CompareItem[], key: keyof BacktestResponse): Set<string> {
  const withResults = items.filter((it) => it.result !== undefined);
  if (withResults.length === 0) return new Set();
  // For all columns, higher is better (max_drawdown: least negative = highest numeric)
  const best = Math.max(...withResults.map((it) => it.result![key] as number));
  return new Set(withResults.filter((it) => (it.result![key] as number) === best).map((it) => it.id));
}

export function CompareTab() {
  const { toast } = useToast();
  const [items, setItems] = useState<CompareItem[]>(DEFAULT_ITEMS);

  const updateItem = (id: string, patch: Partial<CompareItem>) =>
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, ...patch } : it)));

  const addItem = () => {
    const id = String(Date.now());
    setItems((prev) => [
      ...prev,
      { id, symbol: "AAPL", strategy: "rsi", start: "2020-01-01", end: "2024-12-31", positionSizePct: 0.1, loading: false },
    ]);
  };

  const removeItem = (id: string) =>
    setItems((prev) => (prev.length > 1 ? prev.filter((it) => it.id !== id) : prev));

  const runItem = async (id: string) => {
    const item = items.find((it) => it.id === id);
    if (!item) return;
    updateItem(id, { loading: true });
    try {
      const result = await fetchBacktest(item.symbol, item.strategy, item.start, item.end, item.positionSizePct);
      updateItem(id, { result, loading: false });
    } catch (err) {
      toast({ title: "回测失败", description: String(err), variant: "destructive" });
      updateItem(id, { loading: false });
    }
  };

  const runAll = () =>
    items.filter((it) => !it.result).forEach((it) => runItem(it.id));

  const completedItems = items.filter((it) => it.result !== undefined);

  // Build overlay chart data: merge all curves by date index
  const curves = completedItems.map((it) => buildCurve(it.result!));
  const maxLen = Math.max(0, ...curves.map((c) => c.length));
  const chartData = Array.from({ length: maxLen }, (_, i) => {
    const point: Record<string, string | number> = { date: curves[0]?.[i]?.date ?? "" };
    completedItems.forEach((it, ci) => {
      point[it.id] = curves[ci][i]?.value ?? "";
    });
    return point;
  });

  const sharpeBest = bestIndices(items, "sharpe_ratio");
  const returnBest = bestIndices(items, "annual_return");
  const drawdownBest = bestIndices(items, "max_drawdown");
  const tradeBest = bestIndices(items, "trade_count");

  return (
    <div className="space-y-4">
      {/* Rows */}
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-end gap-2">
            <Input
              value={item.symbol}
              onChange={(e) => updateItem(item.id, { symbol: e.target.value.toUpperCase(), result: undefined })}
              className="w-20"
              placeholder="代码"
            />
            <Select
              value={item.strategy}
              onValueChange={(v) => updateItem(item.id, { strategy: v, result: undefined })}
            >
              <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="rsi">RSI</SelectItem>
                <SelectItem value="ma">MA 交叉</SelectItem>
                <SelectItem value="macd">MACD</SelectItem>
              </SelectContent>
            </Select>
            <Input type="date" value={item.start} onChange={(e) => updateItem(item.id, { start: e.target.value, result: undefined })} className="w-36" />
            <Input type="date" value={item.end} onChange={(e) => updateItem(item.id, { end: e.target.value, result: undefined })} className="w-36" />
            <Button variant="outline" size="sm" onClick={() => runItem(item.id)} disabled={item.loading}>
              {item.loading ? "运行中..." : "重新运行"}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => removeItem(item.id)} disabled={items.length === 1}>
              删除
            </Button>
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={addItem}>＋ 添加对比项</Button>
        <Button size="sm" onClick={runAll} disabled={items.every((it) => !!it.result)}>
          运行全部
        </Button>
      </div>

      {completedItems.length === 0 && (
        <p className="text-sm text-muted-foreground">运行回测后显示对比结果</p>
      )}

      {completedItems.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-muted-foreground text-xs">
                  <th className="text-left py-2 pr-4">组合</th>
                  <th className="text-right py-2 pr-4">Sharpe</th>
                  <th className="text-right py-2 pr-4">年化收益</th>
                  <th className="text-right py-2 pr-4">最大回撤</th>
                  <th className="text-right py-2">交易次数</th>
                </tr>
              </thead>
              <tbody>
                {completedItems.map((item) => (
                  <tr key={item.id} className="border-b last:border-0">
                    <td className="py-2 pr-4">{item.symbol} {STRATEGY_LABELS[item.strategy] ?? item.strategy}</td>
                    <td className={`text-right py-2 pr-4 ${ sharpeBest.has(item.id) ? "bg-green-500/10 font-semibold" : "" }`}>
                      {item.result!.sharpe_ratio.toFixed(4)}
                    </td>
                    <td className={`text-right py-2 pr-4 ${ returnBest.has(item.id) ? "bg-green-500/10 font-semibold" : "" }`}>
                      {(item.result!.annual_return * 100).toFixed(2)}%
                    </td>
                    <td className={`text-right py-2 pr-4 ${ drawdownBest.has(item.id) ? "bg-green-500/10 font-semibold" : "" }`}>
                      {(item.result!.max_drawdown * 100).toFixed(2)}%
                    </td>
                    <td className={`text-right py-2 ${ tradeBest.has(item.id) ? "bg-green-500/10 font-semibold" : "" }`}>
                      {item.result!.trade_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} />
              <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip />
              {completedItems.map((item, i) => (
                <Line
                  key={item.id}
                  type="monotone"
                  dataKey={item.id}
                  name={`${item.symbol} ${STRATEGY_LABELS[item.strategy] ?? item.strategy}`}
                  stroke={COLORS[i % COLORS.length]}
                  dot={false}
                  strokeWidth={2}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build passes**

```bash
cd web && npm run build
```
Expected: Build succeeds, no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add web/components/strategies/CompareTab.tsx
git commit -m "feat: CompareTab — multi-strategy comparison with table and overlay chart"
```

---

### Task 4: StrategiesPage — tabbed layout

**Files:**
- Modify: `web/app/strategies/page.tsx`

The current page (45 lines) renders BacktestForm then conditionally BacktestResults + EquityCurve. Replace with a two-tab layout: 概览 (existing content) and 策略对比 (CompareTab).

shadcn Tabs are already used in the project. Import from `@/components/ui/tabs`.

- [ ] **Step 1: Rewrite `web/app/strategies/page.tsx`**

```tsx
"use client";
import { useState } from "react";
import { useToast } from "@/components/ui/use-toast";
import { fetchBacktest } from "@/lib/api";
import type { BacktestResponse } from "@/lib/types";
import { BacktestForm, type Params } from "@/components/strategies/BacktestForm";
import { BacktestResults } from "@/components/strategies/BacktestResults";
import { EquityCurve } from "@/components/strategies/EquityCurve";
import { CompareTab } from "@/components/strategies/CompareTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function StrategiesPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);

  const handleSubmit = async (params: Params) => {
    setLoading(true);
    try {
      const res = await fetchBacktest(
        params.symbol,
        params.strategy,
        params.start,
        params.end,
        params.positionSizePct
      );
      setResult(res);
    } catch (err) {
      toast({ title: "回测失败", description: String(err), variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">策略库</h1>
      <BacktestForm onSubmit={handleSubmit} loading={loading} />
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="compare">策略对比</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 pt-4">
          {result ? (
            <>
              <BacktestResults result={result} />
              <EquityCurve result={result} />
            </>
          ) : (
            <p className="text-sm text-muted-foreground">运行回测后显示结果</p>
          )}
        </TabsContent>

        <TabsContent value="compare" className="pt-4">
          <CompareTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 2: Verify build passes**

```bash
cd web && npm run build
```
Expected: Build succeeds with 7 routes

- [ ] **Step 3: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ -q
```
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add web/app/strategies/page.tsx
git commit -m "feat: strategies page — tabbed layout (概览 + 策略对比)"
```
