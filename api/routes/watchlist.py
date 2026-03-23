from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.schema import get_connection, DEFAULT_DB_PATH

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
