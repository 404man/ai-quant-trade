import json
from db.schema import get_connection
from api.gateways.base import BaseGateway, GatewayStatus, OrderResult, SENSITIVE_FIELDS

_GATEWAY_CLASSES: dict[str, type[BaseGateway]] = {}


def _register_gateways():
    if _GATEWAY_CLASSES:
        return
    from api.gateways.alpaca import AlpacaGateway
    from api.gateways.binance import BinanceGateway
    from api.gateways.futu import FutuGateway
    from api.gateways.ib import IBGateway
    _GATEWAY_CLASSES["alpaca"] = AlpacaGateway
    _GATEWAY_CLASSES["binance"] = BinanceGateway
    _GATEWAY_CLASSES["futu"] = FutuGateway
    _GATEWAY_CLASSES["ib"] = IBGateway


class GatewayManager:
    def __init__(self):
        self._gateways: dict[str, BaseGateway] = {}

    def load_from_db(self, db_path: str) -> None:
        _register_gateways()
        conn = get_connection(db_path)
        try:
            rows = conn.execute("SELECT name FROM gateway_configs").fetchall()
        finally:
            conn.close()
        for row in rows:
            name = row["name"]
            cls = _GATEWAY_CLASSES.get(name)
            if cls:
                self._gateways[name] = cls()

    def get_all(self, db_path: str) -> list[dict]:
        conn = get_connection(db_path)
        try:
            rows = conn.execute("SELECT * FROM gateway_configs ORDER BY name").fetchall()
        finally:
            conn.close()
        result = []
        for row in rows:
            config = json.loads(row["config_json"])
            masked = {k: ("***" if k in SENSITIVE_FIELDS else v) for k, v in config.items()}
            gw = self._gateways.get(row["name"])
            result.append({
                "name": row["name"],
                "label": gw.label if gw else row["name"].title(),
                "enabled": bool(row["enabled"]),
                "status": gw.status if gw else row["status"],
                "config": masked,
            })
        return result

    def save_config(self, name: str, config: dict, enabled: bool, db_path: str) -> None:
        conn = get_connection(db_path)
        try:
            conn.execute(
                "UPDATE gateway_configs SET config_json = ?, enabled = ? WHERE name = ?",
                (json.dumps(config), int(enabled), name),
            )
            conn.commit()
        finally:
            conn.close()

    def connect(self, name: str, db_path: str) -> GatewayStatus:
        gw = self._gateways.get(name)
        if gw is None:
            _register_gateways()
            cls = _GATEWAY_CLASSES.get(name)
            if cls is None:
                raise ValueError(f"Unknown gateway: {name}")
            gw = cls()
            self._gateways[name] = gw
        conn = get_connection(db_path)
        try:
            row = conn.execute("SELECT config_json FROM gateway_configs WHERE name = ?", (name,)).fetchone()
        finally:
            conn.close()
        config = json.loads(row["config_json"]) if row else {}
        try:
            gw.connect(config)
            gw.status = "connected"
        except Exception:
            gw.status = "error"
            self._persist_status(name, "error", db_path)
            raise
        self._persist_status(name, "connected", db_path)
        return "connected"

    def disconnect(self, name: str, db_path: str) -> GatewayStatus:
        gw = self._gateways.get(name)
        if gw is None:
            _register_gateways()
            cls = _GATEWAY_CLASSES.get(name)
            if cls is None:
                raise ValueError(f"Unknown gateway: {name}")
            gw = cls()
            self._gateways[name] = gw
        gw.disconnect()
        gw.status = "disconnected"
        self._persist_status(name, "disconnected", db_path)
        return "disconnected"

    def get_status(self, name: str) -> GatewayStatus:
        gw = self._gateways.get(name)
        if gw is None:
            raise ValueError(f"Unknown gateway: {name}")
        return gw.status

    def route_order(self, name: str, symbol: str, action: str, qty: float) -> OrderResult:
        gw = self._gateways.get(name)
        if gw is None:
            raise ValueError(f"Unknown gateway: {name}")
        return gw.send_order(symbol, action, qty)

    def _persist_status(self, name: str, status: str, db_path: str) -> None:
        conn = get_connection(db_path)
        try:
            conn.execute("UPDATE gateway_configs SET status = ? WHERE name = ?", (status, name))
            conn.commit()
        finally:
            conn.close()


_manager = GatewayManager()
