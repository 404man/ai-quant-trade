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

export interface Params {
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
            <SelectItem value="macd">MACD</SelectItem>
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
