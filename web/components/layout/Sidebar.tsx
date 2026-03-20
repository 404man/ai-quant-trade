"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ApiStatus } from "./ApiStatus";

const navItems = [
  { href: "/live",       label: "实盘" },
  { href: "/strategies", label: "策略库" },
  { href: "/terminal",   label: "交易终端" },
  { href: "/explore",    label: "数据探索" },
  { href: "/messages",   label: "消息中心" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-[220px] flex-col border-r bg-background px-4 py-6">
      <div className="mb-8 text-lg font-semibold tracking-tight">
        AI Quant
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map(({ href, label }) => (
          <Link
            key={href}
            href={href}
            className={`rounded-md px-3 py-2 text-sm transition-colors ${
              pathname === href
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto">
        <ApiStatus />
      </div>
    </aside>
  );
}
