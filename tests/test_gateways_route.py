import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from db.schema import init_db, get_connection
from api.main import app

client = TestClient(app)


@pytest.fixture
def seeded_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    return db_path


def _patch_manager(seeded_db):
    """Return context manager that patches _manager with a fresh instance using seeded_db."""
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(seeded_db)
    return patch("api.routes.gateways._manager", mgr), patch("api.routes.gateways.DEFAULT_DB_PATH", seeded_db)


def test_get_gateways_200(seeded_db):
    p1, p2 = _patch_manager(seeded_db)
    with p1, p2:
        resp = client.get("/gateways")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 4
    names = [g["name"] for g in body]
    assert "alpaca" in names


def test_get_gateways_masks_secrets(seeded_db):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(seeded_db)
    mgr.save_config("alpaca", {"api_key": "PK123", "secret_key": "MYSECRET", "mode": "paper"}, True, seeded_db)
    with patch("api.routes.gateways._manager", mgr), patch("api.routes.gateways.DEFAULT_DB_PATH", seeded_db):
        resp = client.get("/gateways")
    alpaca = [g for g in resp.json() if g["name"] == "alpaca"][0]
    assert alpaca["config"]["secret_key"] == "***"
    assert alpaca["config"]["api_key"] == "PK123"


def test_put_gateway_saves(seeded_db):
    p1, p2 = _patch_manager(seeded_db)
    with p1, p2:
        resp = client.put("/gateways/alpaca", json={"config": {"api_key": "NEW", "secret_key": "SEC"}, "enabled": True})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "alpaca"
    assert body["enabled"] is True


def test_put_gateway_unknown_404(seeded_db):
    p1, p2 = _patch_manager(seeded_db)
    with p1, p2:
        resp = client.put("/gateways/nonexistent", json={"config": {}, "enabled": False})
    assert resp.status_code == 404


def test_connect_success(seeded_db):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(seeded_db)
    mock_gw = MagicMock()
    mock_gw.connect.return_value = None
    mock_gw.status = "disconnected"
    mgr._gateways["alpaca"] = mock_gw
    mgr.save_config("alpaca", {"api_key": "PK"}, True, seeded_db)
    with patch("api.routes.gateways._manager", mgr), patch("api.routes.gateways.DEFAULT_DB_PATH", seeded_db):
        resp = client.post("/gateways/alpaca/connect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"


def test_connect_failure(seeded_db):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(seeded_db)
    mock_gw = MagicMock()
    mock_gw.connect.side_effect = RuntimeError("bad creds")
    mgr._gateways["alpaca"] = mock_gw
    mgr.save_config("alpaca", {"api_key": "bad"}, True, seeded_db)
    with patch("api.routes.gateways._manager", mgr), patch("api.routes.gateways.DEFAULT_DB_PATH", seeded_db):
        resp = client.post("/gateways/alpaca/connect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
    assert "bad creds" in resp.json()["detail"]


def test_connect_unknown_404(seeded_db):
    p1, p2 = _patch_manager(seeded_db)
    with p1, p2:
        resp = client.post("/gateways/nonexistent/connect")
    assert resp.status_code == 404


def test_disconnect_success(seeded_db):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(seeded_db)
    mock_gw = MagicMock()
    mock_gw.disconnect.return_value = None
    mgr._gateways["alpaca"] = mock_gw
    with patch("api.routes.gateways._manager", mgr), patch("api.routes.gateways.DEFAULT_DB_PATH", seeded_db):
        resp = client.post("/gateways/alpaca/disconnect")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"


def test_get_status_200(seeded_db):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(seeded_db)
    mock_gw = MagicMock()
    mock_gw.status = "connected"
    mgr._gateways["alpaca"] = mock_gw
    with patch("api.routes.gateways._manager", mgr), patch("api.routes.gateways.DEFAULT_DB_PATH", seeded_db):
        resp = client.get("/gateways/alpaca/status")
    assert resp.status_code == 200
    assert resp.json() == {"name": "alpaca", "status": "connected"}


def test_get_status_unknown_404(seeded_db):
    p1, p2 = _patch_manager(seeded_db)
    with p1, p2:
        resp = client.get("/gateways/nonexistent/status")
    assert resp.status_code == 404


def test_disconnect_unknown_404(seeded_db):
    p1, p2 = _patch_manager(seeded_db)
    with p1, p2:
        resp = client.post("/gateways/nonexistent/disconnect")
    assert resp.status_code == 404
