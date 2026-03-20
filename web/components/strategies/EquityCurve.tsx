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
        <Tooltip
          formatter={(v) => {
            if (typeof v === "number") return v.toFixed(4);
            if (Array.isArray(v)) return String(v[0] ?? "");
            return String(v ?? "");
          }}
        />
        <Line type="monotone" dataKey="value" stroke="#2563eb" dot={false} strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
