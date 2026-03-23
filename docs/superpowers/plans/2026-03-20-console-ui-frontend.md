# Console UI — Next.js Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Next.js 14 trading console with 5 pages (实盘/策略库/交易终端/数据探索/消息中心) that directly calls the FastAPI backend at `http://localhost:8000`.

**Architecture:** Next.js App Router with a left sidebar layout. All API calls go through `web/lib/api.ts` which fetches directly from FastAPI — no Next.js API routes needed. Pages own state and data fetching; sub-components only render. shadcn/ui for all UI primitives; TradingView lightweight-charts for K-line chart; Recharts for equity curve.

**Tech Stack:** Next.js 14, TypeScript, Tailwind CSS, shadcn/ui, `lightweight-charts` (TradingView), Recharts, `next/navigation`

---

## Prerequisites

Before starting this plan, the backend `GET /confirmations` endpoint must exist (see `2026-03-20-console-ui-backend-confirmations.md`).

FastAPI must be running on `http://localhost:8000` for manual testing during development.

---

## File Structure

```
web/                              ← New directory at stock/web/
├── app/
│   ├── layout.tsx                ← Root layout: sidebar + content area
│   ├── page.tsx                  ← Redirect to /live
│   ├── live/page.tsx             ← 实盘
│   ├── strategies/page.tsx       ← 策略库
│   ├── terminal/page.tsx         ← 交易终端
│   ├── explore/page.tsx          ← 数据探索
│   └── messages/page.tsx         ← 消息中心
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx           ← Nav links + API status
│   │   └── ApiStatus.tsx         ← Polls /health every 30s
│   ├── live/
│   │   ├── AccountSummary.tsx    ← 3 stat cards
│   │   ├── PositionsTable.tsx    ← Positions grid
│   │   └── SignalPanel.tsx       ← Signal query form + results + trade button
│   ├── strategies/
│   │   ├── BacktestForm.tsx      ← Strategy/symbol/dates/size form
│   │   ├── BacktestResults.tsx   ← 5 metric cards
│   │   └── EquityCurve.tsx       ← Recharts LineChart
│   ├── terminal/
│   │   ├── BrokerSelector.tsx    ← Paper/Live toggle (localStorage)
│   │   └── OrderForm.tsx         ← symbol/action/qty + submit result
│   ├── explore/
│   │   ├── ExploreForm.tsx       ← symbol/start/end form
│   │   └── PriceChart.tsx        ← lightweight-charts candlestick
│   └── messages/
│       ├── ConfirmationsTab.tsx  ← Table of confirmation records
│       └── SystemLogTab.tsx      ← In-memory API call log table
├── lib/
│   ├── api.ts                    ← All fetch wrappers
│   └── types.ts                  ← TypeScript interfaces
├── .env.local                    ← NEXT_PUBLIC_API_URL=http://localhost:8000
├── next.config.ts
├── tailwind.config.ts
├── components.json               ← shadcn/ui config
└── package.json
```

---

## Task 1: Project scaffold + layout shell

**Files:**
- Create: `web/` (entire Next.js project)

### Background

Bootstrap Next.js with shadcn/ui, install all dependencies, then build the shell layout (sidebar + routing). All pages will just show a placeholder until later tasks.

The sidebar has 5 nav items. `ApiStatus` polls `GET /health` every 30 seconds and shows a green/red dot.

- [ ] **Step 1: Create Next.js project**

```bash
cd /Users/zakj/Documents/my/stock
npx create-next-app@14 web --typescript --tailwind --eslint --app --no-src-dir --import-alias "@/*"
```

When prompted, accept all defaults.

- [ ] **Step 2: Install dependencies**

```bash
cd /Users/zakj/Documents/my/stock/web
npm install lightweight-charts recharts
npm install @radix-ui/react-tabs @radix-ui/react-select @radix-ui/react-toast
npx shadcn@latest init
```

During `shadcn init`: choose **Default** style, **Zinc** base color, **yes** to CSS variables.

Then add shadcn components:

```bash
npx shadcn@latest add button card input label select tabs badge toast table
```

- [ ] **Step 3: Create `.env.local`**

Create `web/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

- [ ] **Step 4: Create `web/lib/types.ts`**

```typescript
export interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BacktestResponse {
  symbol: string;
  strategy: string;
  start: string;
  end: string;
  sharpe_ratio: number;
  max_drawdown: number;
  annual_return: number;
  trade_count: number;
  avg_holding_days: number;
}

export interface SignalResponse {
  symbol: string;
  action: "buy" | "sell" | "hold";
  score: number;
  size: number;
  rsi_signal: string;
  ma_signal: string;
  sentiment: string;
  sentiment_confidence: number;
  risk_blocked: boolean;
  risk_reason: string | null;
}

export interface TradeResponse {
  status: "submitted" | "blocked" | "cancelled" | "error";
  order_id?: string;
  qty?: number;
  price_estimate?: number;
  reason?: string;
}

export interface ConfirmationRecord {
  order_id: string;
  symbol: string;
  action: string;
  qty: number;
  created_at: string;
  status: "pending" | "confirmed" | "cancelled";
}

export interface ApiLogEntry {
  timestamp: string;
  endpoint: string;
  status: number;
  duration_ms: number;
}
```

- [ ] **Step 5: Create `web/lib/api.ts`**

```typescript
import type {
  BacktestResponse,
  ConfirmationRecord,
  PriceBar,
  SignalResponse,
  TradeResponse,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await apiFetch<{ status: string }>("/health");
    return true;
  } catch {
    return false;
  }
}

export async function fetchPrice(
  symbol: string,
  start: string,
  end: string
): Promise<PriceBar[]> {
  return apiFetch<PriceBar[]>(
    `/data/price?symbol=${symbol}&start=${start}&end=${end}`
  );
}

export async function fetchBacktest(
  symbol: string,
  strategy: string,
  start: string,
  end: string,
  positionSizePct?: number
): Promise<BacktestResponse> {
  const params = new URLSearchParams({ symbol, strategy, start, end });
  if (positionSizePct !== undefined)
    params.set("position_size_pct", String(positionSizePct));
  return apiFetch<BacktestResponse>(`/backtest?${params}`);
}

export async function fetchSignal(
  symbol: string,
  start: string,
  end: string,
  capital?: number
): Promise<SignalResponse> {
  const params = new URLSearchParams({ symbol, start, end });
  if (capital !== undefined) params.set("capital", String(capital));
  return apiFetch<SignalResponse>(`/signal?${params}`);
}

export async function submitTrade(body: {
  symbol: string;
  action: string;
  size: number;
  capital: number;
  start: string;
  end: string;
}): Promise<TradeResponse> {
  return apiFetch<TradeResponse>("/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function fetchConfirmations(): Promise<ConfirmationRecord[]> {
  return apiFetch<ConfirmationRecord[]>("/confirmations");
}
```

- [ ] **Step 6: Create `web/components/layout/ApiStatus.tsx`**

```typescript
"use client";
import { useEffect, useState } from "react";
import { checkHealth } from "@/lib/api";

export function ApiStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const check = async () => setOnline(await checkHealth());
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  if (online === null) return null;

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span
        className={`h-2 w-2 rounded-full ${
          online ? "bg-green-500" : "bg-red-500"
        }`}
      />
      {online ? "API 在线" : "API 离线"}
    </div>
  );
}
```

- [ ] **Step 7: Create `web/components/layout/Sidebar.tsx`**

```typescript
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ApiStatus } from "./ApiStatus";

const navItems = [
  { href: "/live",       label: "实盘" },
  { href: "/strategies", label: "策略库" },
  { href: "/terminal",   label: "交易终端" },
  { href: "/explore",    label: "数据探索" },
  { href: "/messages",   label: "消息中心" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-[220px] flex-col border-r bg-background px-4 py-6">
      <div className="mb-8 text-lg font-semibold tracking-tight">
        AI Quant
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`rounded-md px-3 py-2 text-sm transition-colors ${
              pathname === href
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto">
        <ApiStatus />
      </div>
    </aside>
  );
}
```

- [ ] **Step 8: Create `web/app/layout.tsx`**

```typescript
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI Quant Console",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh">
      <body className={inter.className}>
        <div className="flex h-screen overflow-hidden">
          <Sidebar />
          <main className="flex-1 overflow-auto p-6">{children}</main>
        </div>
        <Toaster />
      </body>
    </html>
  );
}
```

- [ ] **Step 9: Create root redirect `web/app/page.tsx`**

```typescript
import { redirect } from "next/navigation";
export default function Home() {
  redirect("/live");
}
```

- [ ] **Step 10: Create placeholder pages**

Create these 5 files (stubs — will be replaced in later tasks):

`web/app/live/page.tsx`:
```typescript
export default function LivePage() {
  return <h1 className="text-2xl font-bold">实盘</h1>;
}
```

`web/app/strategies/page.tsx`:
```typescript
export default function StrategiesPage() {
  return <h1 className="text-2xl font-bold">策略库</h1>;
}
```

`web/app/terminal/page.tsx`:
```typescript
export default function TerminalPage() {
  return <h1 className="text-2xl font-bold">交易终端</h1>;
}
```

`web/app/explore/page.tsx`:
```typescript
export default function ExplorePage() {
  return <h1 className="text-2xl font-bold">数据探索</h1>;
}
```

`web/app/messages/page.tsx`:
```typescript
export default function MessagesPage() {
  return <h1 className="text-2xl font-bold">消息中心</h1>;
}
```

- [ ] **Step 11: Verify dev server starts**

```bash
cd /Users/zakj/Documents/my/stock/web && npm run dev
```

Open `http://localhost:3000` in browser. Expected: sidebar with 5 nav items, redirects to `/live`, shows "实盘".

- [ ] **Step 12: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/
git commit -m "feat: Next.js scaffold + layout shell + lib/api.ts + lib/types.ts"
```

---

## Task 2: 数据探索页 `/explore`

**Files:**
- Modify: `web/app/explore/page.tsx`
- Create: `web/components/explore/ExploreForm.tsx`
- Create: `web/components/explore/PriceChart.tsx`

### Background

This page is the best starting point because it uses the most distinctive dependency (TradingView lightweight-charts) and lets you verify both data pipelines (`/data/price` and `/backtest`) work end-to-end.

`PriceChart` receives `PriceBar[]` and renders a candlestick chart using TradingView `createChart`. It must be a `"use client"` component and use `useRef` + `useEffect` for chart lifecycle (the library is not React-aware).

`ExploreForm` is a controlled form that calls back with `{symbol, start, end}` on submit.

- [ ] **Step 1: Create `web/components/explore/ExploreForm.tsx`**

```typescript
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  onSubmit: (params: { symbol: string; start: string; end: string }) => void;
  loading: boolean;
}

export function ExploreForm({ onSubmit, loading }: Props) {
  const [symbol, setSymbol] = useState("AAPL");
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState("2024-12-31");

  return (
    <form
      className="flex flex-wrap items-end gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ symbol: symbol.toUpperCase(), start, end });
      }}
    >
      <div className="flex flex-col gap-1">
        <Label>股票代码</Label>
        <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="w-28" />
      </div>
      <div className="flex flex-col gap-1">
        <Label>开始日期</Label>
        <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label>结束日期</Label>
        <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
      </div>
      <Button type="submit" disabled={loading}>
        {loading ? "加载中..." : "查询"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 2: Create `web/components/explore/PriceChart.tsx`**

```typescript
"use client";
import { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";
import type { PriceBar } from "@/lib/types";

interface Props {
  data: PriceBar[];
}

export function PriceChart({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 400,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#333",
      },
      grid: {
        vertLines: { color: "#f0f0f0" },
        horzLines: { color: "#f0f0f0" },
      },
    });

    const series = chart.addCandlestickSeries();
    series.setData(
      data.map((bar) => ({
        time: bar.date,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      }))
    );
    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <div className="flex h-[400px] items-center justify-center text-muted-foreground">
        暂无数据，请查询
      </div>
    );
  }

  return <div ref={containerRef} className="w-full" />;
}
```

- [ ] **Step 3: Replace `web/app/explore/page.tsx`**

```typescript
"use client";
import { useState } from "react";
import { useToast } from "@/components/ui/use-toast";
import { fetchPrice, fetchBacktest } from "@/lib/api";
import type { PriceBar, BacktestResponse } from "@/lib/types";
import { ExploreForm } from "@/components/explore/ExploreForm";
import { PriceChart } from "@/components/explore/PriceChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function ExplorePage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [bars, setBars] = useState<PriceBar[]>([]);
  const [rsiResult, setRsiResult] = useState<BacktestResponse | null>(null);
  const [maResult, setMaResult] = useState<BacktestResponse | null>(null);

  const handleSubmit = async (params: { symbol: string; start: string; end: string }) => {
    setLoading(true);
    try {
      const [prices, rsi, ma] = await Promise.all([
        fetchPrice(params.symbol, params.start, params.end),
        fetchBacktest(params.symbol, "rsi", params.start, params.end),
        fetchBacktest(params.symbol, "ma", params.start, params.end),
      ]);
      setBars(prices);
      setRsiResult(rsi);
      setMaResult(ma);
    } catch (err) {
      toast({ title: "请求失败", description: String(err), variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const metrics: { label: string; key: keyof BacktestResponse }[] = [
    { label: "Sharpe", key: "sharpe_ratio" },
    { label: "最大回撤", key: "max_drawdown" },
    { label: "年化收益", key: "annual_return" },
    { label: "交易次数", key: "trade_count" },
    { label: "平均持仓天数", key: "avg_holding_days" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">数据探索</h1>
      <ExploreForm onSubmit={handleSubmit} loading={loading} />
      <PriceChart data={bars} />
      {(rsiResult || maResult) && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {[{ label: "RSI 策略", result: rsiResult }, { label: "MA 策略", result: maResult }].map(
            ({ label, result }) =>
              result && (
                <Card key={label}>
                  <CardHeader>
                    <CardTitle className="text-base">{label}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <dl className="grid grid-cols-2 gap-2 text-sm">
                      {metrics.map(({ label: ml, key }) => (
                        <div key={key}>
                          <dt className="text-muted-foreground">{ml}</dt>
                          <dd className="font-medium">{String(result[key])}</dd>
                        </div>
                      ))}
                    </dl>
                  </CardContent>
                </Card>
              )
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verify in browser**

With FastAPI running on 8000 and Next.js on 3000:
- Go to `http://localhost:3000/explore`
- Enter AAPL, 2024-01-01, 2024-12-31, click 查询
- Expected: candlestick chart loads, two backtest result cards appear below

- [ ] **Step 5: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/app/explore/ web/components/explore/
git commit -m "feat: 数据探索页 — K线图 + 回测结果对比"
```

---

## Task 3: 策略库页 `/strategies`

**Files:**
- Modify: `web/app/strategies/page.tsx`
- Create: `web/components/strategies/BacktestForm.tsx`
- Create: `web/components/strategies/BacktestResults.tsx`
- Create: `web/components/strategies/EquityCurve.tsx`

### Background

Strategy page runs a single backtest and shows the 5 metrics + a simulated equity curve. The backend doesn't return a per-day returns array, so `EquityCurve` generates a synthetic curve: start at 1.0, apply `annual_return` linearly over the date range. This gives a feel for the curve shape without needing backend changes.

- [ ] **Step 1: Create `web/components/strategies/BacktestForm.tsx`**

```typescript
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Params {
  symbol: string;
  strategy: string;
  start: string;
  end: string;
  positionSizePct: number;
}

interface Props {
  onSubmit: (params: Params) => void;
  loading: boolean;
}

export function BacktestForm({ onSubmit, loading }: Props) {
  const [symbol, setSymbol] = useState("AAPL");
  const [strategy, setStrategy] = useState("rsi");
  const [start, setStart] = useState("2020-01-01");
  const [end, setEnd] = useState("2024-12-31");
  const [positionSizePct, setPositionSizePct] = useState(0.1);

  return (
    <form
      className="flex flex-wrap items-end gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ symbol: symbol.toUpperCase(), strategy, start, end, positionSizePct });
      }}
    >
      <div className="flex flex-col gap-1">
        <Label>股票代码</Label>
        <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="w-28" />
      </div>
      <div className="flex flex-col gap-1">
        <Label>策略</Label>
        <Select value={strategy} onValueChange={setStrategy}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="rsi">RSI</SelectItem>
            <SelectItem value="ma">MA 交叉</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1">
        <Label>开始</Label>
        <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label>结束</Label>
        <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label>仓位 (0.01-1)</Label>
        <Input
          type="number"
          min={0.01}
          max={1}
          step={0.01}
          value={positionSizePct}
          onChange={(e) => setPositionSizePct(Number(e.target.value))}
          className="w-24"
        />
      </div>
      <Button type="submit" disabled={loading}>
        {loading ? "运行中..." : "运行回测"}
      </Button>
    </form>
  );
}
```

- [ ] **Step 2: Create `web/components/strategies/BacktestResults.tsx`**

```typescript
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BacktestResponse } from "@/lib/types";

function fmt(value: number, key: string): string {
  if (key === "max_drawdown" || key === "annual_return") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (key === "sharpe_ratio") return value.toFixed(4);
  if (key === "avg_holding_days") return `${value.toFixed(1)} 天`;
  return String(value);
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
            <p className="text-xl font-semibold">{fmt(result[key] as number, key)}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Create `web/components/strategies/EquityCurve.tsx`**

```typescript
"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import type { BacktestResponse } from "@/lib/types";

function buildCurve(result: BacktestResponse): { date: string; value: number }[] {
  const start = new Date(result.start);
  const end = new Date(result.end);
  const days = Math.ceil((end.getTime() - start.getTime()) / 86_400_000);
  const dailyRate = Math.pow(1 + result.annual_return, 1 / 252) - 1;
  const points: { date: string; value: number }[] = [];
  let value = 1.0;
  for (let i = 0; i <= days; i += Math.max(1, Math.floor(days / 100))) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    points.push({ date: d.toISOString().slice(0, 10), value: parseFloat(value.toFixed(4)) });
    value *= 1 + dailyRate;
  }
  return points;
}

export function EquityCurve({ result }: { result: BacktestResponse }) {
  const data = buildCurve(result);
  return (
    <ResponsiveContainer width="100%" height={250}>
      <LineChart data={data}>
        <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} />
        <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
        <Tooltip formatter={(v: number) => v.toFixed(4)} />
        <Line type="monotone" dataKey="value" stroke="#2563eb" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 4: Replace `web/app/strategies/page.tsx`**

```typescript
"use client";
import { useState } from "react";
import { useToast } from "@/components/ui/use-toast";
import { fetchBacktest } from "@/lib/api";
import type { BacktestResponse } from "@/lib/types";
import { BacktestForm } from "@/components/strategies/BacktestForm";
import { BacktestResults } from "@/components/strategies/BacktestResults";
import { EquityCurve } from "@/components/strategies/EquityCurve";

export default function StrategiesPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResponse | null>(null);

  const handleSubmit = async (params: {
    symbol: string;
    strategy: string;
    start: string;
    end: string;
    positionSizePct: number;
  }) => {
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
      {result && (
        <>
          <BacktestResults result={result} />
          <EquityCurve result={result} />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify in browser**

- Go to `http://localhost:3000/strategies`
- Run RSI on AAPL 2020-2024, click 运行回测
- Expected: 5 metric cards + line chart

- [ ] **Step 6: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/app/strategies/ web/components/strategies/
git commit -m "feat: 策略库页 — 回测表单 + 5指标卡片 + 收益曲线"
```

---

## Task 4: 实盘页 `/live`

**Files:**
- Modify: `web/app/live/page.tsx`
- Create: `web/components/live/AccountSummary.tsx`
- Create: `web/components/live/PositionsTable.tsx`
- Create: `web/components/live/SignalPanel.tsx`

### Background

The live page has three sections. Since we don't have a `GET /positions` endpoint (positions are in SQLite), `AccountSummary` and `PositionsTable` show static placeholder data with a "数据来自本地 DB" note — the real data will come from Phase 5. `SignalPanel` is the interactive part: query a signal and optionally execute the trade.

`SignalPanel` shows a loading skeleton while waiting for `/signal` (which hits Claude API). On result, shows all 7 signal fields + a "执行交易" button that calls `POST /trade`.

- [ ] **Step 1: Create `web/components/live/AccountSummary.tsx`**

```typescript
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  capital: number;
  dailyPnl: number;
  positionCount: number;
}

export function AccountSummary({ capital, dailyPnl, positionCount }: Props) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardHeader className="pb-1 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground font-normal">总资金</CardTitle>
        </CardHeader>
        <CardContent className="pb-4 px-4">
          <p className="text-2xl font-bold">${capital.toLocaleString()}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-1 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground font-normal">当日盈亏</CardTitle>
        </CardHeader>
        <CardContent className="pb-4 px-4">
          <p className={`text-2xl font-bold ${dailyPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
            {dailyPnl >= 0 ? "+" : ""}${dailyPnl.toFixed(2)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-1 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground font-normal">持仓数量</CardTitle>
        </CardHeader>
        <CardContent className="pb-4 px-4">
          <p className="text-2xl font-bold">{positionCount}</p>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Create `web/components/live/PositionsTable.tsx`**

```typescript
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Placeholder — real data from GET /positions in Phase 5
const PLACEHOLDER_POSITIONS = [
  { symbol: "—", qty: "—", avgCost: "—", currentPrice: "—", pnlPct: "—" },
];

export function PositionsTable() {
  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">当前持仓</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>股票</TableHead>
            <TableHead>数量</TableHead>
            <TableHead>成本价</TableHead>
            <TableHead>当前价</TableHead>
            <TableHead>盈亏%</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {PLACEHOLDER_POSITIONS.map((row, i) => (
            <TableRow key={i}>
              <TableCell>{row.symbol}</TableCell>
              <TableCell>{row.qty}</TableCell>
              <TableCell>{row.avgCost}</TableCell>
              <TableCell>{row.currentPrice}</TableCell>
              <TableCell>{row.pnlPct}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground">持仓数据将在 Phase 5 接入 Alpaca 后显示</p>
    </div>
  );
}
```

- [ ] **Step 3: Create `web/components/live/SignalPanel.tsx`**

```typescript
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchSignal, submitTrade } from "@/lib/api";
import type { SignalResponse, TradeResponse } from "@/lib/types";

const ACTION_COLOR: Record<string, string> = {
  buy: "bg-green-100 text-green-800",
  sell: "bg-red-100 text-red-800",
  hold: "bg-gray-100 text-gray-800",
};

export function SignalPanel() {
  const [symbol, setSymbol] = useState("AAPL");
  const [start, setStart] = useState("2024-01-01");
  const [end, setEnd] = useState("2024-12-31");
  const [capital, setCapital] = useState(500);
  const [loading, setLoading] = useState(false);
  const [trading, setTrading] = useState(false);
  const [signal, setSignal] = useState<SignalResponse | null>(null);
  const [tradeResult, setTradeResult] = useState<TradeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleQuery = async () => {
    setLoading(true);
    setSignal(null);
    setTradeResult(null);
    setError(null);
    try {
      const res = await fetchSignal(symbol.toUpperCase(), start, end, capital);
      setSignal(res);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleTrade = async () => {
    if (!signal) return;
    setTrading(true);
    setTradeResult(null);
    try {
      const res = await submitTrade({
        symbol: signal.symbol,
        action: signal.action,
        size: signal.size,
        capital,
        start,
        end,
      });
      setTradeResult(res);
    } catch (err) {
      setError(String(err));
    } finally {
      setTrading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">信号查询</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex flex-col gap-1">
            <Label>股票代码</Label>
            <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} className="w-28" />
          </div>
          <div className="flex flex-col gap-1">
            <Label>开始</Label>
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label>结束</Label>
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1">
            <Label>资金($)</Label>
            <Input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-28"
            />
          </div>
          <Button onClick={handleQuery} disabled={loading}>
            {loading ? "分析中..." : "获取信号"}
          </Button>
        </div>

        {loading && (
          <div className="space-y-2 animate-pulse">
            <div className="h-4 bg-gray-100 rounded w-48" />
            <div className="h-4 bg-gray-100 rounded w-64" />
          </div>
        )}

        {signal && !loading && (
          <div className="space-y-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span className={`rounded-full px-3 py-1 text-sm font-semibold ${ACTION_COLOR[signal.action]}`}>
                {signal.action.toUpperCase()}
              </span>
              <span className="text-sm text-muted-foreground">评分: {signal.score}</span>
              <span className="text-sm text-muted-foreground">仓位: {(signal.size * 100).toFixed(1)}%</span>
              {signal.risk_blocked && (
                <Badge variant="destructive">风控拦截: {signal.risk_reason}</Badge>
              )}
            </div>
            <dl className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm sm:grid-cols-4">
              <div><dt className="text-muted-foreground">RSI信号</dt><dd>{signal.rsi_signal}</dd></div>
              <div><dt className="text-muted-foreground">MA信号</dt><dd>{signal.ma_signal}</dd></div>
              <div><dt className="text-muted-foreground">情绪</dt><dd>{signal.sentiment}</dd></div>
              <div><dt className="text-muted-foreground">置信度</dt><dd>{signal.sentiment_confidence}</dd></div>
            </dl>
            {signal.action !== "hold" && !signal.risk_blocked && (
              <Button onClick={handleTrade} disabled={trading} variant="default">
                {trading ? "执行中..." : `执行交易 (${signal.action.toUpperCase()})`}
              </Button>
            )}
          </div>
        )}

        {tradeResult && (
          <div className="rounded-md border p-3 text-sm">
            <p className="font-medium">交易结果: {tradeResult.status}</p>
            {tradeResult.order_id && <p className="text-muted-foreground">Order ID: {tradeResult.order_id}</p>}
            {tradeResult.reason && <p className="text-muted-foreground">原因: {tradeResult.reason}</p>}
          </div>
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Replace `web/app/live/page.tsx`**

```typescript
import { AccountSummary } from "@/components/live/AccountSummary";
import { PositionsTable } from "@/components/live/PositionsTable";
import { SignalPanel } from "@/components/live/SignalPanel";

export default function LivePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">实盘</h1>
      <AccountSummary capital={500} dailyPnl={0} positionCount={0} />
      <PositionsTable />
      <SignalPanel />
    </div>
  );
}
```

- [ ] **Step 5: Verify in browser**

- Go to `http://localhost:3000/live`
- Enter AAPL, click 获取信号 — expected: loading skeleton then signal result
- If action is buy/sell: "执行交易" button appears

- [ ] **Step 6: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/app/live/ web/components/live/
git commit -m "feat: 实盘页 — 账户概览 + 持仓表格 + 信号面板"
```

---

## Task 5: 交易终端页 `/terminal`

**Files:**
- Modify: `web/app/terminal/page.tsx`
- Create: `web/components/terminal/BrokerSelector.tsx`
- Create: `web/components/terminal/OrderForm.tsx`

### Background

`BrokerSelector` uses `localStorage` to persist the selected broker mode. `OrderForm` submits directly to `POST /trade` with the provided capital amount. The form also accepts `start`/`end` (needed by the backend to price the position size) — use sensible defaults (last year).

- [ ] **Step 1: Create `web/components/terminal/BrokerSelector.tsx`**

```typescript
"use client";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const STORAGE_KEY = "quant-broker-mode";

export function BrokerSelector() {
  const [mode, setMode] = useState<"paper" | "live">("paper");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "paper" || saved === "live") setMode(saved);
  }, []);

  const toggle = () => {
    const next = mode === "paper" ? "live" : "paper";
    setMode(next);
    localStorage.setItem(STORAGE_KEY, next);
  };

  return (
    <div className="flex items-center gap-3">
      <Badge variant={mode === "paper" ? "secondary" : "destructive"}>
        {mode === "paper" ? "Alpaca Paper" : "Alpaca Live"}
      </Badge>
      <Button variant="outline" size="sm" onClick={toggle}>
        切换为 {mode === "paper" ? "Live" : "Paper"}
      </Button>
      {mode === "live" && (
        <p className="text-sm text-red-500 font-medium">⚠️ 实盘模式 — 订单将真实执行</p>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `web/components/terminal/OrderForm.tsx`**

```typescript
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { submitTrade } from "@/lib/api";
import type { TradeResponse } from "@/lib/types";

export function OrderForm() {
  const [symbol, setSymbol] = useState("AAPL");
  const [action, setAction] = useState("buy");
  const [capital, setCapital] = useState(500);
  const [size, setSize] = useState(0.05);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<TradeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const today = new Date().toISOString().slice(0, 10);
  const oneYearAgo = new Date(Date.now() - 365 * 86400_000).toISOString().slice(0, 10);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await submitTrade({
        symbol: symbol.toUpperCase(),
        action,
        size,
        capital,
        start: oneYearAgo,
        end: today,
      });
      setResult(res);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 max-w-sm">
      <div className="flex flex-col gap-1">
        <Label>股票代码</Label>
        <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
      </div>
      <div className="flex flex-col gap-1">
        <Label>方向</Label>
        <Select value={action} onValueChange={setAction}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="buy">买入 BUY</SelectItem>
            <SelectItem value="sell">卖出 SELL</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1">
        <Label>总资金 ($)</Label>
        <Input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))} />
      </div>
      <div className="flex flex-col gap-1">
        <Label>仓位比例 (0.01-1.0)</Label>
        <Input
          type="number"
          min={0.01}
          max={1}
          step={0.01}
          value={size}
          onChange={(e) => setSize(Number(e.target.value))}
        />
      </div>
      <Button type="submit" disabled={loading} className="w-full">
        {loading ? "提交中..." : "提交订单"}
      </Button>

      {result && (
        <div className="rounded-md border p-3 text-sm space-y-1">
          <p className="font-medium">状态: <span className="capitalize">{result.status}</span></p>
          {result.order_id && <p className="text-muted-foreground">Order ID: {result.order_id}</p>}
          {result.qty && <p className="text-muted-foreground">数量: {result.qty} 股</p>}
          {result.price_estimate && <p className="text-muted-foreground">预估价: ${result.price_estimate}</p>}
          {result.reason && <p className="text-muted-foreground">原因: {result.reason}</p>}
        </div>
      )}
      {error && <p className="text-sm text-red-500">{error}</p>}
    </form>
  );
}
```

- [ ] **Step 3: Replace `web/app/terminal/page.tsx`**

```typescript
import { BrokerSelector } from "@/components/terminal/BrokerSelector";
import { OrderForm } from "@/components/terminal/OrderForm";

export default function TerminalPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">交易终端</h1>
      <BrokerSelector />
      <OrderForm />
    </div>
  );
}
```

- [ ] **Step 4: Verify in browser**

- Go to `http://localhost:3000/terminal`
- Toggle broker mode — badge changes, refreshing page persists choice
- Submit an order — see result card

- [ ] **Step 5: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/app/terminal/ web/components/terminal/
git commit -m "feat: 交易终端页 — 经纪商切换 + 下单表单"
```

---

## Task 6: 消息中心页 `/messages`

**Files:**
- Modify: `web/app/messages/page.tsx`
- Create: `web/components/messages/ConfirmationsTab.tsx`
- Create: `web/components/messages/SystemLogTab.tsx`

### Background

`ConfirmationsTab` fetches `GET /confirmations` on mount and refreshes every 10 seconds.

`SystemLogTab` receives `logs: ApiLogEntry[]` as a prop — the logs are stored in the parent page's state and updated by a callback exposed to sibling components (not needed for Phase 5, so keep it simple: the page just holds an empty log array for now, ready for future wiring).

Status badges: `pending` = yellow, `confirmed` = green, `cancelled` = gray.

- [ ] **Step 1: Create `web/components/messages/ConfirmationsTab.tsx`**

```typescript
"use client";
import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { fetchConfirmations } from "@/lib/api";
import type { ConfirmationRecord } from "@/lib/types";

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-800",
};

export function ConfirmationsTab() {
  const [records, setRecords] = useState<ConfirmationRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await fetchConfirmations();
      setRecords(data);
    } catch {
      // silent — no toast spam on background refresh
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <p className="text-sm text-muted-foreground">加载中...</p>;
  if (records.length === 0) return <p className="text-sm text-muted-foreground">暂无确认记录</p>;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>时间</TableHead>
          <TableHead>代码</TableHead>
          <TableHead>方向</TableHead>
          <TableHead>数量</TableHead>
          <TableHead>状态</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {records.map((r) => (
          <TableRow key={r.order_id}>
            <TableCell className="text-xs">{r.created_at.slice(0, 19).replace("T", " ")}</TableCell>
            <TableCell className="font-medium">{r.symbol}</TableCell>
            <TableCell>{r.action.toUpperCase()}</TableCell>
            <TableCell>{r.qty}</TableCell>
            <TableCell>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[r.status] ?? ""}`}>
                {r.status}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Create `web/components/messages/SystemLogTab.tsx`**

```typescript
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ApiLogEntry } from "@/lib/types";

export function SystemLogTab({ logs }: { logs: ApiLogEntry[] }) {
  if (logs.length === 0) {
    return <p className="text-sm text-muted-foreground">本次会话暂无 API 调用记录</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>时间</TableHead>
          <TableHead>端点</TableHead>
          <TableHead>状态码</TableHead>
          <TableHead>耗时(ms)</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log, i) => (
          <TableRow key={i}>
            <TableCell className="text-xs">{log.timestamp}</TableCell>
            <TableCell className="font-mono text-xs">{log.endpoint}</TableCell>
            <TableCell>
              <span className={log.status < 400 ? "text-green-600" : "text-red-600"}>
                {log.status}
              </span>
            </TableCell>
            <TableCell>{log.duration_ms}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 3: Replace `web/app/messages/page.tsx`**

```typescript
"use client";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmationsTab } from "@/components/messages/ConfirmationsTab";
import { SystemLogTab } from "@/components/messages/SystemLogTab";
import type { ApiLogEntry } from "@/lib/types";

export default function MessagesPage() {
  const [logs] = useState<ApiLogEntry[]>([]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">消息中心</h1>
      <Tabs defaultValue="confirmations">
        <TabsList>
          <TabsTrigger value="confirmations">交易通知</TabsTrigger>
          <TabsTrigger value="logs">系统日志</TabsTrigger>
        </TabsList>
        <TabsContent value="confirmations" className="mt-4">
          <ConfirmationsTab />
        </TabsContent>
        <TabsContent value="logs" className="mt-4">
          <SystemLogTab logs={logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
```

- [ ] **Step 4: Verify in browser**

- Go to `http://localhost:3000/messages`
- 交易通知 tab: shows table (empty if no trades, or real data if trades exist)
- 系统日志 tab: shows "本次会话暂无 API 调用记录"

- [ ] **Step 5: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/app/messages/ web/components/messages/
git commit -m "feat: 消息中心页 — 交易通知 + 系统日志 tabs"
```

---

## Completion Criteria

- [ ] `npm run dev` starts without errors
- [ ] All 5 pages render without crashing
- [ ] `/` redirects to `/live`
- [ ] Sidebar highlights active route
- [ ] `/explore`: K线图加载 AAPL 数据，回测结果显示
- [ ] `/strategies`: 回测表单提交后显示指标卡片 + 收益曲线
- [ ] `/live`: 信号面板返回结果（含 loading skeleton）
- [ ] `/terminal`: 经纪商切换持久化；下单表单提交显示结果
- [ ] `/messages`: 交易通知自动刷新，系统日志 tab 存在
- [ ] API 离线时导航栏底部显示红色"API 离线"
