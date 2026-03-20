import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ApiLogEntry } from "@/lib/types";

export function SystemLogTab({ logs }: { logs: ApiLogEntry[] }) {
  if (logs.length === 0) {
    return <p className="text-sm text-muted-foreground">本次会话暂无 API 调用记录</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>时间</TableHead>
          <TableHead>端点</TableHead>
          <TableHead>状态码</TableHead>
          <TableHead>耗时(ms)</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {logs.map((log, i) => (
          <TableRow key={i}>
            <TableCell className="text-xs">{log.timestamp}</TableCell>
            <TableCell className="font-mono text-xs">{log.endpoint}</TableCell>
            <TableCell>
              <span className={log.status < 400 ? "text-green-600" : "text-red-600"}>
                {log.status}
              </span>
            </TableCell>
            <TableCell>{log.duration_ms}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
