from fastapi import APIRouter, HTTPException
from api.services.data_service import DataService
from api.services.signal_service import SignalService
from api.services.risk_service import RiskGate

router = APIRouter()


@router.get("/signal")
def get_signal(
    symbol: str,
    start: str,
    end: str,
    capital: float = 500.0,
    daily_loss: float = 0.0,
    current_positions: int = 0,
):
    data_svc = DataService()
    signal_svc = SignalService()
    risk_gate = RiskGate()

    prices = data_svc.fetch(symbol.upper(), start, end)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

    signal = dict(signal_svc.get_signal(symbol.upper(), prices))

    risk_blocked = False
    risk_reason = None

    if signal["action"] in ("buy", "sell"):
        proposed_value = signal["size"] * capital
        risk_result = risk_gate.check(
            capital=capital,
            daily_loss=daily_loss,
            current_positions=current_positions,
            proposed_trade_value=proposed_value,
        )
        if not risk_result.allowed:
            signal["action"] = "hold"
            risk_blocked = True
            risk_reason = risk_result.reason

    return {
        "symbol": symbol.upper(),
        **signal,
        "risk_blocked": risk_blocked,
        "risk_reason": risk_reason,
    }
