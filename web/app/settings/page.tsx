"use client";
import { useEffect, useState } from "react";
import { fetchGateways } from "@/lib/api";
import { GatewayList } from "@/components/settings/GatewayList";
import { GatewayDetail } from "@/components/settings/GatewayDetail";
import type { GatewayConfig } from "@/lib/types";

export default function SettingsPage() {
  const [gateways, setGateways] = useState<GatewayConfig[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await fetchGateways();
      setGateways(data);
      if (!selected && data.length > 0) setSelected(data[0].name);
    } catch {
      // API offline — show empty state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const selectedGateway = gateways.find((g) => g.name === selected);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">设置</h1>
        <div className="flex gap-6">
          <div className="w-[160px] space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-9 rounded-md bg-accent animate-pulse" />
            ))}
          </div>
          <div className="flex-1 space-y-3">
            <div className="h-8 w-48 rounded bg-accent animate-pulse" />
            <div className="h-10 w-80 rounded bg-accent animate-pulse" />
            <div className="h-10 w-80 rounded bg-accent animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>
      <div className="flex">
        <GatewayList gateways={gateways} selected={selected} onSelect={setSelected} />
        {selectedGateway ? (
          <GatewayDetail gateway={selectedGateway} onUpdated={load} />
        ) : (
          <div className="flex-1 pl-6 text-muted-foreground">选择一个交易接口</div>
        )}
      </div>
    </div>
  );
}
