from fastapi import APIRouter
from api.services.sentiment_service import SentimentService

router = APIRouter()


@router.get("/sentiment")
def get_sentiment(symbol: str):
    svc = SentimentService()
    return svc.get_sentiment(symbol.upper())
