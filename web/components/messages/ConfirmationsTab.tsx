"use client";
import { useEffect, useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fetchConfirmations } from "@/lib/api";
import type { ConfirmationRecord } from "@/lib/types";

const STATUS_BADGE: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-800",
};

export function ConfirmationsTab() {
  const [records, setRecords] = useState<ConfirmationRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await fetchConfirmations();
      setRecords(data);
    } catch {
      // silent — no toast spam on background refresh
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  if (loading) return <p className="text-sm text-muted-foreground">加载中...</p>;
  if (records.length === 0) return <p className="text-sm text-muted-foreground">暂无确认记录</p>;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>时间</TableHead>
          <TableHead>代码</TableHead>
          <TableHead>方向</TableHead>
          <TableHead>数量</TableHead>
          <TableHead>状态</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {records.map((r) => (
          <TableRow key={r.order_id}>
            <TableCell className="text-xs">{r.created_at.slice(0, 19).replace("T", " ")}</TableCell>
            <TableCell className="font-medium">{r.symbol}</TableCell>
            <TableCell>{r.action.toUpperCase()}</TableCell>
            <TableCell>{r.qty}</TableCell>
            <TableCell>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_BADGE[r.status] ?? ""}`}>
                {r.status}
              </span>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
