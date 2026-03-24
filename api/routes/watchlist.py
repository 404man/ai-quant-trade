import os
import requests
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from db.schema import get_connection, DEFAULT_DB_PATH

_POLYGON_KEY = os.getenv("POLYGON_API_KEY", "")

router = APIRouter()


class WatchlistAdd(BaseModel):
    symbol: str
    notes: str = ""


@router.get("/watchlist")
def get_watchlist():
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT symbol, notes, added_at FROM watchlist ORDER BY added_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/watchlist")
def add_to_watchlist(req: WatchlistAdd):
    symbol = req.symbol.upper()
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        existing = conn.execute(
            "SELECT 1 FROM watchlist WHERE symbol = ?", (symbol,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail=f"{symbol} already in watchlist")
        conn.execute(
            "INSERT INTO watchlist (symbol, notes, added_at) VALUES (?, ?, ?)",
            (symbol, req.notes, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        return {"symbol": symbol, "notes": req.notes, "status": "added"}
    finally:
        conn.close()


@router.get("/watchlist/search")
def search_tickers(q: str = Query(..., min_length=1)):
    """Search for ticker symbols using Polygon.io reference API."""
    polygon_key = os.getenv("POLYGON_API_KEY", "")
    if not polygon_key:
        raise HTTPException(status_code=503, detail="Ticker search requires POLYGON_API_KEY")
    try:
        resp = requests.get(
            "https://api.polygon.io/v3/reference/tickers",
            params={
                "search": q,
                "active": "true",
                "market": "stocks",
                "limit": 10,
                "apiKey": polygon_key,
            },
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        return [{"symbol": r["ticker"], "name": r.get("name", "")} for r in results]
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Search failed: {e}")


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(symbol: str):
    symbol = symbol.upper()
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        cursor = conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"{symbol} not in watchlist")
        return {"symbol": symbol, "status": "removed"}
    finally:
        conn.close()
