import { AccountSummary } from "@/components/live/AccountSummary";
import { PositionsTable } from "@/components/live/PositionsTable";
import { SignalPanel } from "@/components/live/SignalPanel";

export default function LivePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">实盘</h1>
      <AccountSummary capital={500} dailyPnl={0} positionCount={0} />
      <PositionsTable />
      <SignalPanel />
    </div>
  );
}
