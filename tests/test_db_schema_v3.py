import sqlite3
import pytest
from db.schema import init_db, get_connection


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_positions_table_exists(db):
    conn = get_connection(db)
    try:
        conn.execute("SELECT symbol, qty, avg_entry_price, side FROM positions LIMIT 1")
    finally:
        conn.close()


def test_daily_loss_table_exists(db):
    conn = get_connection(db)
    try:
        conn.execute("SELECT trade_date, loss_usd FROM daily_loss LIMIT 1")
    finally:
        conn.close()


def test_pending_confirmations_table_exists(db):
    conn = get_connection(db)
    try:
        conn.execute(
            "SELECT order_id, symbol, action, qty, created_at, status "
            "FROM pending_confirmations LIMIT 1"
        )
    finally:
        conn.close()


def test_pending_confirmations_default_status(db):
    conn = get_connection(db)
    try:
        conn.execute(
            "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at) "
            "VALUES ('test-1', 'AAPL', 'buy', 1.0, '2026-01-01T09:00:00')"
        )
        conn.commit()
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'test-1'"
        ).fetchone()
        assert row["status"] == "pending"
    finally:
        conn.close()
