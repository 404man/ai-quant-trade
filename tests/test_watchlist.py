import pytest
from fastapi.testclient import TestClient
from api.main import app
from db.schema import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def _patch_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    init_db(db)
    monkeypatch.setattr("api.routes.watchlist.DEFAULT_DB_PATH", db)


def test_empty_watchlist():
    resp = client.get("/watchlist")
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_symbol():
    resp = client.post("/watchlist", json={"symbol": "aapl", "notes": "tech"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "AAPL"
    assert data["notes"] == "tech"


def test_add_duplicate():
    client.post("/watchlist", json={"symbol": "TSLA"})
    resp = client.post("/watchlist", json={"symbol": "tsla"})
    assert resp.status_code == 409


def test_list_after_add():
    client.post("/watchlist", json={"symbol": "AAPL"})
    client.post("/watchlist", json={"symbol": "TSLA"})
    resp = client.get("/watchlist")
    symbols = [r["symbol"] for r in resp.json()]
    assert "AAPL" in symbols
    assert "TSLA" in symbols


def test_delete_symbol():
    client.post("/watchlist", json={"symbol": "GOOG"})
    resp = client.delete("/watchlist/GOOG")
    assert resp.status_code == 200
    # Verify removed
    items = client.get("/watchlist").json()
    assert all(r["symbol"] != "GOOG" for r in items)


def test_delete_nonexistent():
    resp = client.delete("/watchlist/XYZ")
    assert resp.status_code == 404
