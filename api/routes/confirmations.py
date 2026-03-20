from fastapi import APIRouter
from db.schema import DEFAULT_DB_PATH, get_connection

router = APIRouter()


@router.get("/confirmations")
def get_confirmations():
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT order_id, symbol, action, qty, created_at, status "
            "FROM pending_confirmations "
            "ORDER BY created_at DESC "
            "LIMIT 50"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
