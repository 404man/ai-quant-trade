import type {
  BacktestResponse,
  ConfirmationRecord,
  PriceBar,
  SignalResponse,
  TradeResponse,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await apiFetch<{ status: string }>("/health");
    return true;
  } catch {
    return false;
  }
}

export async function fetchPrice(
  symbol: string,
  start: string,
  end: string
): Promise<PriceBar[]> {
  return apiFetch<PriceBar[]>(
    `/data/price?symbol=${symbol}&start=${start}&end=${end}`
  );
}

export async function fetchBacktest(
  symbol: string,
  strategy: string,
  start: string,
  end: string,
  positionSizePct?: number
): Promise<BacktestResponse> {
  const params = new URLSearchParams({ symbol, strategy, start, end });
  if (positionSizePct !== undefined)
    params.set("position_size_pct", String(positionSizePct));
  return apiFetch<BacktestResponse>(`/backtest?${params}`);
}

export async function fetchSignal(
  symbol: string,
  start: string,
  end: string,
  capital?: number
): Promise<SignalResponse> {
  const params = new URLSearchParams({ symbol, start, end });
  if (capital !== undefined) params.set("capital", String(capital));
  return apiFetch<SignalResponse>(`/signal?${params}`);
}

export async function submitTrade(body: {
  symbol: string;
  action: string;
  size: number;
  capital: number;
  start: string;
  end: string;
}): Promise<TradeResponse> {
  return apiFetch<TradeResponse>("/trade", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function fetchConfirmations(): Promise<ConfirmationRecord[]> {
  return apiFetch<ConfirmationRecord[]>("/confirmations");
}
