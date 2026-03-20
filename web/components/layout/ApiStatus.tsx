"use client";
import { useEffect, useState } from "react";
import { checkHealth } from "@/lib/api";

export function ApiStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const check = async () => setOnline(await checkHealth());
    check();
    const id = setInterval(check, 30_000);
    return () => clearInterval(id);
  }, []);

  if (online === null) return null;

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span
        className={`h-2 w-2 rounded-full ${
          online ? "bg-green-500" : "bg-red-500"
        }`}
      />
      {online ? "API 在线" : "API 离线"}
    </div>
  );
}
