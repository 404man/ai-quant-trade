import math
import time
import uuid
from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from api.services.data_service import DataService
from api.services.risk_service import RiskGate
from api.services.trade_service import TradeService
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


def _insert_pending(order_id: str, symbol: str, action: str, qty: float, db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, symbol, action, qty, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _poll_confirmation(order_id: str, db_path: str = DEFAULT_DB_PATH) -> str:
    """Poll until status is 'confirmed' or 'cancelled', or timeout. Returns final status string."""
    deadline = time.time() + CONFIRMATION_TIMEOUT_SECS
    while time.time() < deadline:
        status = get_confirmation_status(order_id, db_path=db_path)
        if status in ("confirmed", "cancelled"):
            return status
        time.sleep(POLL_INTERVAL_SECS)
    return "timeout"


@router.post("/trade")
def post_trade(req: TradeRequest):
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

    outcome = _poll_confirmation(order_id)

    if outcome == "confirmed":
        alpaca_order_id = trade_svc.submit_order(req.symbol.upper(), req.action, qty)
        return {"status": "submitted", "order_id": alpaca_order_id, "qty": qty, "price_estimate": last_price}

    reason = "user_rejected" if outcome == "cancelled" else "timeout"
    send_cancellation_notice(order_id=order_id, symbol=req.symbol.upper(), reason=reason)
    return {"status": "cancelled", "reason": reason}
