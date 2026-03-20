"use client";
import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmationsTab } from "@/components/messages/ConfirmationsTab";
import { SystemLogTab } from "@/components/messages/SystemLogTab";
import type { ApiLogEntry } from "@/lib/types";

export default function MessagesPage() {
  const [logs] = useState<ApiLogEntry[]>([]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">消息中心</h1>
      <Tabs defaultValue="confirmations">
        <TabsList>
          <TabsTrigger value="confirmations">交易通知</TabsTrigger>
          <TabsTrigger value="logs">系统日志</TabsTrigger>
        </TabsList>
        <TabsContent value="confirmations" className="mt-4">
          <ConfirmationsTab />
        </TabsContent>
        <TabsContent value="logs" className="mt-4">
          <SystemLogTab logs={logs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
