import { BrokerSelector } from "@/components/terminal/BrokerSelector";
import { OrderForm } from "@/components/terminal/OrderForm";

export default function TerminalPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">交易终端</h1>
      <BrokerSelector />
      <OrderForm />
    </div>
  );
}
