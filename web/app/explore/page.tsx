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
    setBars([]);
    setRsiResult(null);
    setMaResult(null);
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
