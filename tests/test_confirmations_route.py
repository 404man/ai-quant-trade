import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from api.main import app
from db.schema import init_db, get_connection

client = TestClient(app)


@pytest.fixture
def seeded_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("ord-1", "AAPL", "buy", 1.0, "2026-01-01T09:00:00", "confirmed"),
    )
    conn.execute(
        "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("ord-2", "TSLA", "sell", 2.0, "2026-01-02T10:00:00", "pending"),
    )
    conn.commit()
    conn.close()
    return db_path


def test_confirmations_returns_200(seeded_db):
    with patch("api.routes.confirmations.DEFAULT_DB_PATH", seeded_db):
        resp = client.get("/confirmations")
    assert resp.status_code == 200


def test_confirmations_returns_list(seeded_db):
    with patch("api.routes.confirmations.DEFAULT_DB_PATH", seeded_db):
        resp = client.get("/confirmations")
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2


def test_confirmations_sorted_newest_first(seeded_db):
    with patch("api.routes.confirmations.DEFAULT_DB_PATH", seeded_db):
        resp = client.get("/confirmations")
    body = resp.json()
    # ord-2 has later created_at, should be first
    assert body[0]["order_id"] == "ord-2"
    assert body[1]["order_id"] == "ord-1"


def test_confirmations_required_fields(seeded_db):
    with patch("api.routes.confirmations.DEFAULT_DB_PATH", seeded_db):
        resp = client.get("/confirmations")
    row = resp.json()[0]
    assert {"order_id", "symbol", "action", "qty", "created_at", "status"}.issubset(row.keys())


def test_confirmations_empty_returns_empty_list(tmp_path):
    db_path = str(tmp_path / "empty.db")
    init_db(db_path)
    with patch("api.routes.confirmations.DEFAULT_DB_PATH", db_path):
        resp = client.get("/confirmations")
    assert resp.status_code == 200
    assert resp.json() == []
