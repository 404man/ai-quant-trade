# api/routes/positions.py
from fastapi import APIRouter
from api.services.trade_service import TradeService

router = APIRouter()


@router.get("/positions")
def get_positions():
    trade_svc = TradeService()
    positions = trade_svc.get_positions()
    return {
        "positions": positions,
        "count": len(positions),
    }
