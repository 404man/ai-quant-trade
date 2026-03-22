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
