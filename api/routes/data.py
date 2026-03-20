from fastapi import APIRouter, HTTPException
from api.services.data_service import DataService

router = APIRouter()


@router.get("/data/price")
def get_price(symbol: str, start: str, end: str):
    svc = DataService()
    try:
        return svc.fetch(symbol.upper(), start, end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
