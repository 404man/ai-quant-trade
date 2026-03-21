"use client";
import { useState, useEffect } from "react";
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
import { saveGateway, connectGateway, disconnectGateway } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";
import type { GatewayConfig } from "@/lib/types";

interface FieldDef {
  key: string;
  label: string;
  type: "text" | "password" | "select";
  options?: string[];
  placeholder?: string;
}

const GATEWAY_FIELDS: Record<string, FieldDef[]> = {
  alpaca: [
    { key: "api_key", label: "API Key", type: "text" },
    { key: "secret_key", label: "Secret Key", type: "password", placeholder: "已保存，输入新值可更新" },
    { key: "mode", label: "模式", type: "select", options: ["paper", "live"] },
  ],
  binance: [
    { key: "api_key", label: "API Key", type: "text" },
    { key: "api_secret", label: "API Secret", type: "password", placeholder: "已保存，输入新值可更新" },
  ],
  futu: [
    { key: "host", label: "Host", type: "text", placeholder: "127.0.0.1" },
    { key: "port", label: "Port", type: "text", placeholder: "11111" },
  ],
  ib: [
    { key: "host", label: "Host", type: "text", placeholder: "127.0.0.1" },
    { key: "port", label: "Port", type: "text", placeholder: "7497" },
  ],
};

const STUB_GATEWAYS = new Set(["futu", "ib"]);
const STUB_MESSAGES: Record<string, string> = {
  futu: "需先在本地运行 FutuOpenD 程序（默认端口 11111）",
  ib: "需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）",
};

interface Props {
  gateway: GatewayConfig;
  onUpdated: () => void;
}

export function GatewayDetail({ gateway, onUpdated }: Props) {
  const { toast } = useToast();
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initial: Record<string, string> = {};
    const fields = GATEWAY_FIELDS[gateway.name] ?? [];
    for (const f of fields) {
      const val = gateway.config[f.key];
      initial[f.key] = val && val !== "***" ? val : "";
    }
    setForm(initial);
    setError(null);
  }, [gateway.name, gateway.config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const config: Record<string, string> = {};
      for (const [k, v] of Object.entries(form)) {
        if (v) config[k] = v;
      }
      await saveGateway(gateway.name, config, true);
      toast({ description: "配置已保存" });
      onUpdated();
    } catch (err) {
      toast({ description: `保存失败: ${err}`, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const res = await connectGateway(gateway.name);
      if (res.status === "error") {
        setError(res.detail ?? "连接失败");
      }
      onUpdated();
    } catch (err) {
      setError(String(err));
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      await disconnectGateway(gateway.name);
      onUpdated();
    } catch (err) {
      setError(String(err));
    } finally {
      setConnecting(false);
    }
  };

  const fields = GATEWAY_FIELDS[gateway.name] ?? [];

  return (
    <div className="flex-1 pl-6 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{gateway.label}</h2>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            gateway.status === "connected"
              ? "bg-green-900/50 text-green-400"
              : gateway.status === "error"
                ? "bg-red-900/50 text-red-400"
                : "bg-zinc-800 text-zinc-400"
          }`}
        >
          {gateway.status === "connected" ? "已连接" : gateway.status === "error" ? "错误" : "未连接"}
        </span>
      </div>

      {STUB_GATEWAYS.has(gateway.name) && (
        <p className="text-sm text-amber-500 bg-amber-950/30 rounded-md px-3 py-2">
          {STUB_MESSAGES[gateway.name]}
        </p>
      )}

      <div className="space-y-3 max-w-sm">
        {fields.map((f) =>
          f.type === "select" ? (
            <div key={f.key} className="flex flex-col gap-1">
              <Label>{f.label}</Label>
              <Select value={form[f.key] || f.options?.[0] || ""} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {f.options?.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div key={f.key} className="flex flex-col gap-1">
              <Label>{f.label}</Label>
              <Input
                type={f.type === "password" ? "password" : "text"}
                placeholder={f.placeholder}
                value={form[f.key] || ""}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
              />
            </div>
          )
        )}
      </div>

      <div className="flex gap-2 max-w-sm">
        <Button onClick={handleSave} disabled={saving} variant="outline" className="flex-1">
          {saving ? "保存中..." : "保存"}
        </Button>
        {gateway.status === "connected" ? (
          <Button onClick={handleDisconnect} disabled={connecting} variant="destructive" className="flex-1">
            {connecting ? "断开中..." : "断开"}
          </Button>
        ) : (
          <Button onClick={handleConnect} disabled={connecting} className="flex-1">
            {connecting ? "连接中..." : "连接"}
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
}
