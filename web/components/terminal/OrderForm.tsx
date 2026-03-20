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
