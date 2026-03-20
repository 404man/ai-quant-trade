from fastapi import APIRouter
from api.services.data_service import DataService

router = APIRouter()


@router.get("/data/price")
def get_price(symbol: str, start: str, end: str):
    svc = DataService()
    return svc.fetch(symbol.upper(), start, end)
