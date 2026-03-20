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
