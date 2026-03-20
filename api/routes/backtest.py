from fastapi import APIRouter, HTTPException
from api.services.data_service import DataService
from api.services.backtest_service import BacktestService

router = APIRouter()


@router.get("/backtest")
def run_backtest(symbol: str, strategy: str, start: str, end: str):
    data_svc = DataService()
    backtest_svc = BacktestService()

    prices = data_svc.fetch(symbol.upper(), start, end)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

    try:
        result = backtest_svc.run(prices, strategy=strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "symbol": symbol.upper(),
        "strategy": strategy,
        "start": start,
        "end": end,
        **result,
    }
