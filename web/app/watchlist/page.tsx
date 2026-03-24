"use client";

import { useEffect, useRef, useState } from "react";
import { fetchWatchlist, addToWatchlist, removeFromWatchlist, searchTickers } from "@/lib/api";
import type { WatchlistItem, TickerResult } from "@/lib/types";

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [symbol, setSymbol] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search state
  const [suggestions, setSuggestions] = useState<TickerResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debouncedSymbol = useDebounce(symbol, 300);
  const wrapperRef = useRef<HTMLDivElement>(null);

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

  // Fetch suggestions when symbol input changes
  useEffect(() => {
    const q = debouncedSymbol.trim();
    if (q.length < 1) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    let cancelled = false;
    setSearching(true);
    searchTickers(q)
      .then((results) => {
        if (!cancelled) {
          setSuggestions(results);
          setShowSuggestions(results.length > 0);
        }
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      })
      .finally(() => {
        if (!cancelled) setSearching(false);
      });
    return () => { cancelled = true; };
  }, [debouncedSymbol]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const selectSuggestion = (ticker: TickerResult) => {
    setSymbol(ticker.symbol);
    setSuggestions([]);
    setShowSuggestions(false);
  };

  const handleAdd = async () => {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    try {
      setError(null);
      await addToWatchlist(s, notes.trim());
      setSymbol("");
      setNotes("");
      setSuggestions([]);
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
        <div className="space-y-1" ref={wrapperRef}>
          <label className="text-sm text-muted-foreground">股票代码</label>
          <div className="relative">
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              onKeyDown={(e) => {
                if (e.key === "Enter") { setShowSuggestions(false); handleAdd(); }
                if (e.key === "Escape") setShowSuggestions(false);
              }}
              placeholder="AAPL"
              className="h-9 w-40 rounded-md border bg-background px-3 text-sm uppercase"
            />
            {searching && (
              <span className="absolute right-2 top-2 text-xs text-muted-foreground">...</span>
            )}
            {showSuggestions && (
              <ul className="absolute z-10 mt-1 w-64 rounded-md border bg-background shadow-md text-sm">
                {suggestions.map((t) => (
                  <li
                    key={t.symbol}
                    onMouseDown={() => selectSuggestion(t)}
                    className="flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-accent"
                  >
                    <span className="font-mono font-medium w-16 shrink-0">{t.symbol}</span>
                    <span className="truncate text-muted-foreground">{t.name}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
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
