# api/main.py
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from api.auth import verify_api_key
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router
from api.routes.sentiment import router as sentiment_router
from api.routes.signal import router as signal_router
from api.routes.trade import router as trade_router
from api.routes.confirmations import router as confirmations_router
from api.routes.gateways import router as gateways_router
from api.routes.positions import router as positions_router
from db.schema import init_db, DEFAULT_DB_PATH
from api.services.gateway_manager import _manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, load gateways, sync positions
    init_db(DEFAULT_DB_PATH)
    _manager.load_from_db(DEFAULT_DB_PATH)
    try:
        from api.services.trade_service import TradeService
        TradeService().sync_positions()
    except Exception:
        pass  # Alpaca creds not configured — skip sync
    yield


app = FastAPI(
    title="AI Quant System",
    version="0.1.0",
    lifespan=lifespan,
)

_auth = [Depends(verify_api_key)]

app.include_router(data_router, dependencies=_auth)
app.include_router(backtest_router, dependencies=_auth)
app.include_router(sentiment_router, dependencies=_auth)
app.include_router(signal_router, dependencies=_auth)
app.include_router(trade_router, dependencies=_auth)
app.include_router(confirmations_router, dependencies=_auth)
app.include_router(gateways_router, dependencies=_auth)
app.include_router(positions_router, dependencies=_auth)


@app.get("/health")
def health():
    """Health check — no auth required."""
    return {"status": "ok"}
