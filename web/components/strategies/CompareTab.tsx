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

  // Build overlay chart data: merge all curves by index
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
