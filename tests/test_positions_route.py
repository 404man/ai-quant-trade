# tests/test_positions_route.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from db.schema import init_db, get_connection
from api.main import app

client = TestClient(app)


@pytest.fixture
def seeded_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def test_positions_empty(seeded_db):
    with patch("api.routes.positions.TradeService") as MockTS:
        instance = MockTS.return_value
        instance.get_positions.return_value = []
        resp = client.get("/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["positions"] == []
    assert body["count"] == 0


def test_positions_with_data(seeded_db):
    positions = [
        {"symbol": "AAPL", "qty": 5.0, "avg_entry_price": 178.5, "side": "long"},
        {"symbol": "TSLA", "qty": 3.0, "avg_entry_price": 245.0, "side": "long"},
    ]
    with patch("api.routes.positions.TradeService") as MockTS:
        instance = MockTS.return_value
        instance.get_positions.return_value = positions
        resp = client.get("/positions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert body["positions"][0]["symbol"] == "AAPL"
