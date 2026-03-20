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
