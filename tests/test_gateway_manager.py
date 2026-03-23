import json
import pytest
from unittest.mock import MagicMock, patch
from db.schema import init_db, get_connection


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


def test_gateway_configs_table_created(db_path):
    conn = get_connection(db_path)
    rows = conn.execute("SELECT name FROM gateway_configs ORDER BY name").fetchall()
    conn.close()
    names = [r["name"] for r in rows]
    assert names == ["alpaca", "binance", "futu", "ib"]


def test_gateway_configs_defaults(db_path):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM gateway_configs WHERE name = 'alpaca'").fetchone()
    conn.close()
    assert row["enabled"] == 0
    assert row["config_json"] == "{}"
    assert row["status"] == "disconnected"


def test_load_from_db(db_path):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    assert "futu" in mgr._gateways
    assert "ib" in mgr._gateways


def test_save_config(db_path):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    mgr.save_config("alpaca", {"api_key": "PK123", "secret_key": "SK456", "mode": "paper"}, True, db_path)
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM gateway_configs WHERE name = 'alpaca'").fetchone()
    conn.close()
    assert row["enabled"] == 1
    config = json.loads(row["config_json"])
    assert config["api_key"] == "PK123"
    assert config["secret_key"] == "SK456"


def test_get_all_masks_secrets(db_path):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    mgr.save_config("alpaca", {"api_key": "PK123", "secret_key": "SK456", "mode": "paper"}, True, db_path)
    all_gw = mgr.get_all(db_path)
    alpaca = [g for g in all_gw if g["name"] == "alpaca"][0]
    assert alpaca["config"]["api_key"] == "PK123"
    assert alpaca["config"]["secret_key"] == "***"


def test_route_order_unknown_gateway(db_path):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    with pytest.raises(ValueError):
        mgr.route_order("nonexistent", "AAPL", "buy", 1.0)


def test_route_order_dispatches_to_adapter(db_path):
    from api.services.gateway_manager import GatewayManager
    from api.gateways.base import OrderResult
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    mock_gw = MagicMock()
    mock_gw.send_order.return_value = OrderResult(
        status="submitted", order_id="ord-1", qty=10.0, price_estimate=150.0, reason=None
    )
    mgr._gateways["alpaca"] = mock_gw
    result = mgr.route_order("alpaca", "AAPL", "buy", 10.0)
    mock_gw.send_order.assert_called_once_with("AAPL", "buy", 10.0)
    assert result.order_id == "ord-1"


def test_connect_persists_status(db_path):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    mock_gw = MagicMock()
    mock_gw.connect.return_value = None
    mgr._gateways["alpaca"] = mock_gw
    mgr.save_config("alpaca", {"api_key": "PK", "secret_key": "SK", "mode": "paper"}, True, db_path)
    status = mgr.connect("alpaca", db_path)
    assert status == "connected"
    conn = get_connection(db_path)
    row = conn.execute("SELECT status FROM gateway_configs WHERE name = 'alpaca'").fetchone()
    conn.close()
    assert row["status"] == "connected"


def test_connect_failure_persists_error(db_path):
    from api.services.gateway_manager import GatewayManager
    mgr = GatewayManager()
    mgr.load_from_db(db_path)
    mock_gw = MagicMock()
    mock_gw.connect.side_effect = RuntimeError("bad key")
    mgr._gateways["alpaca"] = mock_gw
    mgr.save_config("alpaca", {"api_key": "bad"}, True, db_path)
    with pytest.raises(RuntimeError):
        mgr.connect("alpaca", db_path)
    conn = get_connection(db_path)
    row = conn.execute("SELECT status FROM gateway_configs WHERE name = 'alpaca'").fetchone()
    conn.close()
    assert row["status"] == "error"
