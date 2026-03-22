import asyncio
import math
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.data_service import DataService
from api.services.gateway_manager import _manager
from api.services.risk_service import RiskGate
from api.services.trade_service import TradeService
from api.services.webhook_service import WebhookService
from db.schema import DEFAULT_DB_PATH, get_connection
from tg.handlers import get_confirmation_status, send_cancellation_notice, send_confirmation

router = APIRouter()

CONFIRMATION_TIMEOUT_SECS = 300  # 5 minutes
POLL_INTERVAL_SECS = 2


class TradeRequest(BaseModel):
    symbol: str
    action: str          # "buy" | "sell"
    size: float          # fraction of capital, e.g. 0.05
    capital: float       # total portfolio capital in $
    start: str           # YYYY-MM-DD for price fetch
    end: str             # YYYY-MM-DD for price fetch
    gateway: str = "alpaca"


def _insert_pending(order_id: str, symbol: str, action: str, qty: float, db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, symbol, action, qty, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


async def _poll_confirmation(order_id: str, db_path: str = DEFAULT_DB_PATH) -> str:
    """Poll until status is 'confirmed' or 'cancelled', or timeout. Returns final status string."""
    deadline = asyncio.get_event_loop().time() + CONFIRMATION_TIMEOUT_SECS
    while asyncio.get_event_loop().time() < deadline:
        status = get_confirmation_status(order_id, db_path=db_path)
        if status in ("confirmed", "cancelled"):
            return status
        await asyncio.sleep(POLL_INTERVAL_SECS)
    return "timeout"


@router.post("/trade")
async def post_trade(req: TradeRequest):
    today = date.today().isoformat()
    trade_svc = TradeService()
    data_svc = DataService()
    risk_gate = RiskGate()

    prices = data_svc.fetch(req.symbol.upper(), req.start, req.end)
    if not prices:
        return {"status": "error", "reason": f"No price data for {req.symbol}"}

    last_price = prices[-1]["close"]
    qty = max(1, math.floor(req.size * req.capital / last_price))
    proposed_value = qty * last_price

    daily_loss = trade_svc.get_daily_loss(today)
    position_count = trade_svc.get_position_count()

    risk_result = risk_gate.check(
        capital=req.capital,
        daily_loss=daily_loss,
        current_positions=position_count,
        proposed_trade_value=proposed_value,
    )
    if not risk_result.allowed:
        WebhookService().push("risk_alert", {
            "symbol": req.symbol.upper(),
            "reason": risk_result.reason,
            "capital": req.capital,
            "daily_loss": daily_loss,
        })
        return {"status": "blocked", "reason": risk_result.reason}

    order_id = str(uuid.uuid4())
    _insert_pending(order_id, req.symbol.upper(), req.action, qty)
    send_confirmation(
        order_id=order_id,
        symbol=req.symbol.upper(),
        action=req.action,
        qty=qty,
        price_estimate=last_price,
    )

    outcome = await _poll_confirmation(order_id)

    if outcome == "confirmed":
        try:
            gw_result = _manager.route_order(req.gateway, req.symbol.upper(), req.action, qty)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Unknown gateway: {req.gateway}")
        alpaca_order_id = gw_result.order_id
        # Record estimated loss as 0 at submission time; actual P&L tracked separately
        trade_svc.record_loss(today, 0.0)
        WebhookService().push("order_status", {
            "order_id": alpaca_order_id,
            "symbol": req.symbol.upper(),
            "action": req.action,
            "status": "submitted",
            "qty": qty,
            "price_estimate": last_price,
        })
        return {"status": "submitted", "order_id": alpaca_order_id, "qty": qty, "price_estimate": last_price}

    reason = "user_rejected" if outcome == "cancelled" else "timeout"
    send_cancellation_notice(order_id=order_id, symbol=req.symbol.upper(), reason=reason)
    WebhookService().push("order_status", {
        "order_id": order_id,
        "symbol": req.symbol.upper(),
        "action": req.action,
        "status": "cancelled",
        "qty": qty,
        "price_estimate": last_price,
        "reason": reason,
    })
    return {"status": "cancelled", "reason": reason}
