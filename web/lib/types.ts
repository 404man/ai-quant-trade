export interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BacktestResponse {
  symbol: string;
  strategy: string;
  start: string;
  end: string;
  sharpe_ratio: number;
  max_drawdown: number;
  annual_return: number;
  trade_count: number;
  avg_holding_days: number;
}

export interface SignalResponse {
  symbol: string;
  action: "buy" | "sell" | "hold";
  score: number;
  size: number;
  rsi_signal: string;
  ma_signal: string;
  sentiment: string;
  sentiment_confidence: number;
  risk_blocked: boolean;
  risk_reason: string | null;
}

export interface TradeResponse {
  status: "submitted" | "blocked" | "cancelled" | "error";
  order_id?: string;
  qty?: number;
  price_estimate?: number;
  reason?: string;
}

export interface ConfirmationRecord {
  order_id: string;
  symbol: string;
  action: string;
  qty: number;
  created_at: string;
  status: "pending" | "confirmed" | "cancelled";
}

export interface ApiLogEntry {
  timestamp: string;
  endpoint: string;
  status: number;
  duration_ms: number;
}

export interface GatewayConfig {
  name: string;
  label: string;
  enabled: boolean;
  status: "connected" | "disconnected" | "error";
  config: Record<string, string>;
}
