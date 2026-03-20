import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  capital: number;
  dailyPnl: number;
  positionCount: number;
}

export function AccountSummary({ capital, dailyPnl, positionCount }: Props) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <Card>
        <CardHeader className="pb-1 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground font-normal">总资金</CardTitle>
        </CardHeader>
        <CardContent className="pb-4 px-4">
          <p className="text-2xl font-bold">${capital.toLocaleString()}</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-1 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground font-normal">当日盈亏</CardTitle>
        </CardHeader>
        <CardContent className="pb-4 px-4">
          <p className={`text-2xl font-bold ${dailyPnl >= 0 ? "text-green-600" : "text-red-600"}`}>
            {dailyPnl >= 0 ? "+" : ""}${dailyPnl.toFixed(2)}
          </p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="pb-1 pt-4 px-4">
          <CardTitle className="text-xs text-muted-foreground font-normal">持仓数量</CardTitle>
        </CardHeader>
        <CardContent className="pb-4 px-4">
          <p className="text-2xl font-bold">{positionCount}</p>
        </CardContent>
      </Card>
    </div>
  );
}
