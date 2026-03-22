import logging
import os

import httpx

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self):
        self.url = os.environ.get("OPENCLAW_HOOK_URL", "")
        self.token = os.environ.get("OPENCLAW_HOOK_TOKEN", "")

    def push(self, event_type: str, data: dict) -> None:
        """Push an event to OpenClaw webhook. Fails silently."""
        if not self.url or not self.token:
            return
        message = self._format_message(event_type, data)
        try:
            httpx.post(
                self.url,
                json={"message": message, "name": f"stock-{event_type}"},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5.0,
            )
        except Exception as e:
            logger.warning("Webhook push failed: %s", e)

    def _format_message(self, event_type: str, data: dict) -> str:
        formatters = {
            "signal": self._fmt_signal,
            "risk_alert": self._fmt_risk_alert,
            "order_status": self._fmt_order_status,
            "daily_summary": self._fmt_daily_summary,
        }
        fmt = formatters.get(event_type)
        return fmt(data) if fmt else str(data)

    def _fmt_signal(self, d: dict) -> str:
        action_zh = "买入" if d["action"] == "buy" else "卖出"
        pct = round(d["size"] * 100, 1)
        return f"交易信号：{d['symbol']} {action_zh}，仓位 {pct}%，评分 {d['score']}"

    def _fmt_risk_alert(self, d: dict) -> str:
        return f"风控警报：{d['symbol']} 交易被拦截 — {d['reason']}"

    def _fmt_order_status(self, d: dict) -> str:
        if d["status"] == "submitted":
            action_zh = "买入" if d["action"] == "buy" else "卖出"
            return f"订单成交：{d['symbol']} {action_zh} {d['qty']} 股 @ ${d['price_estimate']}"
        reason = d.get("reason", d["status"])
        return f"订单取消：{d['symbol']} — {reason}"

    def _fmt_daily_summary(self, d: dict) -> str:
        lines = [f"每日摘要 ({d['date']})"]
        if d.get("account_balance") is not None:
            lines.append(f"账户余额: ${d['account_balance']:.2f}")
        lines.append(f"当日盈亏: ${d['daily_pnl']:.2f}")
        if d["positions"]:
            lines.append("持仓:")
            for p in d["positions"]:
                lines.append(f"  {p['symbol']} {p['qty']}股 {p['side']} @ ${p['avg_entry_price']}")
        else:
            lines.append("持仓: 空仓")
        return "\n".join(lines)
