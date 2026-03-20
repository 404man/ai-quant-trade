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
  const [start, setStart] = useState(() => new Date(Date.now() - 365 * 86400_000).toISOString().slice(0, 10));
  const [end, setEnd] = useState(() => new Date().toISOString().slice(0, 10));
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
    setError(null);
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
