import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { BacktestResponse } from "@/lib/types";

type MetricKey = "sharpe_ratio" | "max_drawdown" | "annual_return" | "trade_count" | "avg_holding_days";

function fmt(value: number, key: MetricKey): string {
  if (key === "max_drawdown" || key === "annual_return") {
    return `${(value * 100).toFixed(2)}%`;
  }
  if (key === "sharpe_ratio") return value.toFixed(4);
  if (key === "avg_holding_days") return `${value.toFixed(1)} 天`;
  return String(value);
}

function valueColor(value: number, key: MetricKey): string {
  if (key === "annual_return") return value > 0 ? "text-green-500" : "text-red-500";
  if (key === "max_drawdown") return "text-red-500";
  return "";
}

function SharpeBadge({ value }: { value: number }) {
  if (value >= 2.0) {
    return <span className="ml-2 text-xs font-medium px-1.5 py-0.5 rounded bg-green-100 text-green-700">优秀</span>;
  }
  if (value >= 1.0) {
    return <span className="ml-2 text-xs font-medium px-1.5 py-0.5 rounded bg-yellow-100 text-yellow-700">良好</span>;
  }
  return null;
}

export function BacktestResults({ result }: { result: BacktestResponse }) {
  const metrics = [
    { label: "Sharpe Ratio", key: "sharpe_ratio" },
    { label: "最大回撤", key: "max_drawdown" },
    { label: "年化收益", key: "annual_return" },
    { label: "交易次数", key: "trade_count" },
    { label: "平均持仓", key: "avg_holding_days" },
  ] as const;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {metrics.map(({ label, key }) => (
        <Card key={key}>
          <CardHeader className="pb-1 pt-4 px-4">
            <CardTitle className="text-xs text-muted-foreground font-normal">{label}</CardTitle>
          </CardHeader>
          <CardContent className="pb-4 px-4">
            <p className={`text-xl font-semibold flex items-center ${valueColor(result[key], key)}`}>
              {fmt(result[key], key)}
              {key === "sharpe_ratio" && <SharpeBadge value={result[key]} />}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
