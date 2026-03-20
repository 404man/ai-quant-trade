from fastapi import FastAPI
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router
from api.routes.sentiment import router as sentiment_router

app = FastAPI(title="AI Quant System", version="0.1.0")

app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(sentiment_router)


@app.get("/health")
def health():
    return {"status": "ok"}
