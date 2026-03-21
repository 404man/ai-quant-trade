"use client";
import type { GatewayConfig } from "@/lib/types";

const statusColor: Record<string, string> = {
  connected: "bg-green-500",
  disconnected: "bg-zinc-500",
  error: "bg-red-500",
};

interface Props {
  gateways: GatewayConfig[];
  selected: string | null;
  onSelect: (name: string) => void;
}

export function GatewayList({ gateways, selected, onSelect }: Props) {
  return (
    <div className="flex flex-col gap-1 w-[160px] border-r pr-4">
      <h3 className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
        交易接口
      </h3>
      {gateways.map((gw) => (
        <button
          key={gw.name}
          onClick={() => onSelect(gw.name)}
          className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors text-left ${
            selected === gw.name
              ? "bg-accent text-accent-foreground font-medium"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full flex-shrink-0 ${statusColor[gw.status] ?? "bg-zinc-500"}`}
          />
          {gw.label}
        </button>
      ))}
    </div>
  );
}
