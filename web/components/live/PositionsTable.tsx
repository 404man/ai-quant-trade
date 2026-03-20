import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

// Placeholder — real data from GET /positions in Phase 5
const PLACEHOLDER_POSITIONS = [
  { symbol: "—", qty: "—", avgCost: "—", currentPrice: "—", pnlPct: "—" },
];

export function PositionsTable() {
  return (
    <div className="space-y-2">
      <h2 className="text-sm font-medium text-muted-foreground">当前持仓</h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>股票</TableHead>
            <TableHead>数量</TableHead>
            <TableHead>成本价</TableHead>
            <TableHead>当前价</TableHead>
            <TableHead>盈亏%</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {PLACEHOLDER_POSITIONS.map((row, i) => (
            <TableRow key={i}>
              <TableCell>{row.symbol}</TableCell>
              <TableCell>{row.qty}</TableCell>
              <TableCell>{row.avgCost}</TableCell>
              <TableCell>{row.currentPrice}</TableCell>
              <TableCell>{row.pnlPct}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="text-xs text-muted-foreground">持仓数据将在 Phase 5 接入 Alpaca 后显示</p>
    </div>
  );
}
