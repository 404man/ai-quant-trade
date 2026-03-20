"use client";
import { useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries } from "lightweight-charts";
import type { PriceBar } from "@/lib/types";

interface Props {
  data: PriceBar[];
}

export function PriceChart({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
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

    const series = chart.addSeries(CandlestickSeries);
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

    return () => {
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

  return <div ref={containerRef} className="w-full h-[400px]" />;
}
