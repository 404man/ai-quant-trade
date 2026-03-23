"use client";

import { useEffect, useState } from "react";
import { fetchWatchlist, addToWatchlist, removeFromWatchlist } from "@/lib/api";
import type { WatchlistItem } from "@/lib/types";

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [symbol, setSymbol] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchWatchlist();
      setItems(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async () => {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    try {
      setError(null);
      await addToWatchlist(s, notes.trim());
      setSymbol("");
      setNotes("");
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to add");
    }
  };

  const handleRemove = async (sym: string) => {
    try {
      setError(null);
      await removeFromWatchlist(sym);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to remove");
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">自选列表</h1>

      {/* Add form */}
      <div className="flex items-end gap-3">
        <div className="space-y-1">
          <label className="text-sm text-muted-foreground">股票代码</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="AAPL"
            className="h-9 w-28 rounded-md border bg-background px-3 text-sm uppercase"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm text-muted-foreground">备注</label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="tech leader"
            className="h-9 w-48 rounded-md border bg-background px-3 text-sm"
          />
        </div>
        <button
          onClick={handleAdd}
          disabled={!symbol.trim()}
          className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          添加
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* List */}
      {loading ? (
        <p className="text-sm text-muted-foreground">加载中...</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          自选列表为空，添加几只股票开始追踪
        </p>
      ) : (
        <div className="rounded-md border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-2 text-left font-medium">代码</th>
                <th className="px-4 py-2 text-left font-medium">备注</th>
                <th className="px-4 py-2 text-left font-medium">添加时间</th>
                <th className="px-4 py-2 text-right font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.symbol} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono font-medium">
                    {item.symbol}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {item.notes || "—"}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">
                    {new Date(item.added_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => handleRemove(item.symbol)}
                      className="text-destructive hover:underline"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        共 {items.length} 只 · OpenClaw 每日扫描基于此列表
      </p>
    </div>
  );
}
