# api/routes/daily_summary.py
from datetime import date

from fastapi import APIRouter

from api.services.trade_service import TradeService
from api.services.webhook_service import WebhookService

router = APIRouter()


@router.post("/daily-summary")
def post_daily_summary():
    trade_svc = TradeService()
    positions = trade_svc.get_positions()
    daily_loss = trade_svc.get_daily_loss(date.today().isoformat())

    account_balance = None
    try:
        account = trade_svc._get_client().get_account()
        account_balance = float(account.equity)
    except Exception:
        pass

    WebhookService().push("daily_summary", {
        "positions": positions,
        "daily_pnl": -daily_loss,
        "account_balance": account_balance,
        "date": date.today().isoformat(),
    })
    return {"status": "sent"}
