from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router
from api.routes.sentiment import router as sentiment_router
from api.routes.signal import router as signal_router
from api.routes.trade import router as trade_router
from api.routes.confirmations import router as confirmations_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: sync positions from Alpaca (no-op if creds not set)
    try:
        from api.services.trade_service import TradeService
        TradeService().sync_positions()
    except Exception:
        pass  # Alpaca creds not configured — skip sync
    yield


app = FastAPI(title="AI Quant System", version="0.1.0", lifespan=lifespan)

app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(sentiment_router)
app.include_router(signal_router)
app.include_router(trade_router)
app.include_router(confirmations_router)


@app.get("/health")
def health():
    return {"status": "ok"}
