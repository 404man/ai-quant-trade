# Gateway Settings — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unified Gateway abstraction layer with 4 adapters (Alpaca, Binance, Futu stub, IB stub), configuration API, and frontend settings page.

**Architecture:** `BaseGateway` ABC → 4 adapters → `GatewayManager` singleton → FastAPI routes → Next.js `/settings` page. Config stored in SQLite `gateway_configs` table. Existing `POST /trade` updated to route through GatewayManager.

**Tech Stack:** Python 3.10, FastAPI, SQLite, ccxt (Binance), Next.js 14, TypeScript, shadcn/ui

---

## File Structure

```
api/gateways/__init__.py         ← CREATE: empty, makes gateways a package
api/gateways/base.py             ← CREATE: BaseGateway ABC + OrderResult dataclass
api/gateways/alpaca.py           ← CREATE: AlpacaGateway (wraps TradeService.submit_order)
api/gateways/binance.py          ← CREATE: BinanceGateway (ccxt REST API)
api/gateways/futu.py             ← CREATE: FutuGateway (stub, raises RuntimeError)
api/gateways/ib.py               ← CREATE: IBGateway (stub, raises RuntimeError)
api/services/gateway_manager.py  ← CREATE: GatewayManager singleton
api/routes/gateways.py           ← CREATE: 5 gateway API routes
db/schema.py                     ← MODIFY: add gateway_configs table + seed data
api/main.py                      ← MODIFY: lifespan init + register router
api/routes/trade.py              ← MODIFY: add gateway param, use _manager.route_order()
requirements.txt                 ← MODIFY: add ccxt>=4.0.0
web/lib/types.ts                 ← MODIFY: add GatewayConfig interface
web/lib/api.ts                   ← MODIFY: add 5 gateway API functions
web/components/layout/Sidebar.tsx← MODIFY: add "设置" nav item
web/app/settings/page.tsx        ← CREATE: settings page with dual-column layout
web/components/settings/GatewayList.tsx   ← CREATE: left panel gateway list
web/components/settings/GatewayDetail.tsx ← CREATE: right panel config form
tests/test_gateway_manager.py    ← CREATE: GatewayManager unit tests
tests/test_gateways_route.py     ← CREATE: gateway route tests
tests/test_alpaca_gateway.py     ← CREATE: AlpacaGateway unit tests
tests/test_binance_gateway.py    ← CREATE: BinanceGateway unit tests
tests/test_trade_route.py        ← MODIFY: update mocks for _manager.route_order
```

---

## Task 1: Database schema + BaseGateway + GatewayManager

**Files:**
- Modify: `db/schema.py`
- Create: `api/gateways/__init__.py`
- Create: `api/gateways/base.py`
- Create: `api/gateways/futu.py`
- Create: `api/gateways/ib.py`
- Create: `api/services/gateway_manager.py`
- Test: `tests/test_gateway_manager.py`

### Background

This task builds the core foundation: the DB table, the abstract base class, the two stub gateways, and the GatewayManager that ties everything together. The real adapters (Alpaca, Binance) come in later tasks.

The existing `db/schema.py` has 7 tables created in `init_db()` (lines 19–82). We add one more table plus seed data.

`GatewayManager` is a module-level singleton (`_manager = GatewayManager()`). It holds a `dict[str, BaseGateway]` of adapter instances and reads/writes config from SQLite. Routes import `_manager` directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gateway_manager.py`:

```python
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
    assert "alpaca" in mgr._gateways
    assert "binance" in mgr._gateways
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
    with pytest.raises(KeyError):
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_gateway_manager.py -v 2>&1 | head -30
```

Expected: ImportError or table-not-found errors.

- [ ] **Step 3: Add `gateway_configs` table to `db/schema.py`**

Add after the `pending_confirmations` table creation (after line 82, before `conn.commit()`):

```python
        conn.execute("""
            CREATE TABLE IF NOT EXISTS gateway_configs (
                name        TEXT PRIMARY KEY,
                config_json TEXT NOT NULL DEFAULT '{}',
                enabled     INTEGER NOT NULL DEFAULT 0,
                status      TEXT NOT NULL DEFAULT 'disconnected'
            )
        """)
        for gw_name in ("alpaca", "binance", "futu", "ib"):
            conn.execute(
                "INSERT OR IGNORE INTO gateway_configs (name) VALUES (?)",
                (gw_name,),
            )
```

- [ ] **Step 4: Create `api/gateways/__init__.py`**

Empty file.

- [ ] **Step 5: Create `api/gateways/base.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

GatewayStatus = Literal["connected", "disconnected", "error"]

SENSITIVE_FIELDS = {"secret_key", "api_secret"}


@dataclass
class OrderResult:
    status: str
    order_id: str | None
    qty: float | None
    price_estimate: float | None
    reason: str | None


class BaseGateway(ABC):
    name: str
    label: str
    status: GatewayStatus = "disconnected"

    @abstractmethod
    def connect(self, config: dict) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult: ...

    def get_status(self) -> GatewayStatus:
        return self.status
```

- [ ] **Step 6: Create `api/gateways/futu.py`**

```python
from api.gateways.base import BaseGateway, OrderResult


class FutuGateway(BaseGateway):
    name = "futu"
    label = "富途"

    def connect(self, config: dict) -> None:
        raise RuntimeError("需先在本地运行 FutuOpenD 程序（默认端口 11111）")

    def disconnect(self) -> None:
        raise RuntimeError("需先在本地运行 FutuOpenD 程序（默认端口 11111）")

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        raise RuntimeError("需先在本地运行 FutuOpenD 程序（默认端口 11111）")
```

- [ ] **Step 7: Create `api/gateways/ib.py`**

```python
from api.gateways.base import BaseGateway, OrderResult


class IBGateway(BaseGateway):
    name = "ib"
    label = "Interactive Brokers"

    def connect(self, config: dict) -> None:
        raise RuntimeError("需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）")

    def disconnect(self) -> None:
        raise RuntimeError("需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）")

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        raise RuntimeError("需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）")
```

- [ ] **Step 8: Create `api/services/gateway_manager.py`**

```python
import json
from db.schema import get_connection
from api.gateways.base import BaseGateway, GatewayStatus, OrderResult, SENSITIVE_FIELDS

# Registry: gateway name -> class
_GATEWAY_CLASSES: dict[str, type[BaseGateway]] = {}


def _register_gateways():
    """Import and register all gateway classes. Called once on first load_from_db."""
    if _GATEWAY_CLASSES:
        return
    from api.gateways.futu import FutuGateway
    from api.gateways.ib import IBGateway
    _GATEWAY_CLASSES["futu"] = FutuGateway
    _GATEWAY_CLASSES["ib"] = IBGateway
    # Alpaca and Binance added in later tasks:
    # from api.gateways.alpaca import AlpacaGateway
    # from api.gateways.binance import BinanceGateway


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
            raise KeyError(f"Unknown gateway: {name}")
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
            raise KeyError(f"Unknown gateway: {name}")
        gw.disconnect()
        gw.status = "disconnected"
        self._persist_status(name, "disconnected", db_path)
        return "disconnected"

    def get_status(self, name: str) -> GatewayStatus:
        gw = self._gateways.get(name)
        if gw is None:
            raise KeyError(f"Unknown gateway: {name}")
        return gw.status

    def route_order(self, name: str, symbol: str, action: str, qty: float) -> OrderResult:
        gw = self._gateways.get(name)
        if gw is None:
            raise KeyError(f"Unknown gateway: {name}")
        return gw.send_order(symbol, action, qty)

    def _persist_status(self, name: str, status: str, db_path: str) -> None:
        conn = get_connection(db_path)
        try:
            conn.execute("UPDATE gateway_configs SET status = ? WHERE name = ?", (status, name))
            conn.commit()
        finally:
            conn.close()


_manager = GatewayManager()
```

- [ ] **Step 9: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_gateway_manager.py -v
```

Expected: 9 PASSED

- [ ] **Step 10: Full suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

Expected: all existing tests + 9 new = all passed

- [ ] **Step 11: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add db/schema.py api/gateways/ api/services/gateway_manager.py tests/test_gateway_manager.py
git commit -m "feat: BaseGateway + GatewayManager + gateway_configs table + stub gateways"
```

---

## Task 2: AlpacaGateway adapter

**Files:**
- Create: `api/gateways/alpaca.py`
- Modify: `api/services/gateway_manager.py` (register AlpacaGateway)
- Test: `tests/test_alpaca_gateway.py`

### Background

AlpacaGateway wraps the existing `TradeService.submit_order()` logic. Per spec, `send_order()` delegates to `TradeService().submit_order()` internally. The `connect()` method validates credentials by creating a `TradingClient` and calling `get_account()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_alpaca_gateway.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def test_alpaca_connect_success():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    mock_client = MagicMock()
    with patch("api.gateways.alpaca.TradingClient", return_value=mock_client):
        gw.connect({"api_key": "PK", "secret_key": "SK", "mode": "paper"})
    assert gw.status == "connected"
    mock_client.get_account.assert_called_once()


def test_alpaca_connect_failure():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    with patch("api.gateways.alpaca.TradingClient", side_effect=Exception("bad creds")):
        with pytest.raises(Exception, match="bad creds"):
            gw.connect({"api_key": "bad", "secret_key": "bad", "mode": "paper"})


def test_alpaca_send_order():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    mock_client = MagicMock()
    mock_order = MagicMock()
    mock_order.id = "ord-abc-123"
    mock_client.submit_order.return_value = mock_order
    with patch("api.gateways.alpaca.TradingClient", return_value=mock_client):
        gw.connect({"api_key": "PK", "secret_key": "SK", "mode": "paper"})
    result = gw.send_order("AAPL", "buy", 10.0)
    assert result.status == "submitted"
    assert result.order_id == "ord-abc-123"
    assert result.qty == 10.0


def test_alpaca_disconnect():
    from api.gateways.alpaca import AlpacaGateway
    gw = AlpacaGateway()
    mock_client = MagicMock()
    with patch("api.gateways.alpaca.TradingClient", return_value=mock_client):
        gw.connect({"api_key": "PK", "secret_key": "SK", "mode": "paper"})
    gw.disconnect()
    assert gw.status == "disconnected"
    assert gw._client is None
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_alpaca_gateway.py -v 2>&1 | head -20
```

Expected: ImportError

- [ ] **Step 3: Create `api/gateways/alpaca.py`**

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from api.gateways.base import BaseGateway, OrderResult
from api.services.trade_service import TradeService


class AlpacaGateway(BaseGateway):
    name = "alpaca"
    label = "Alpaca"

    def __init__(self):
        self._client: TradingClient | None = None

    def connect(self, config: dict) -> None:
        paper = config.get("mode", "paper") == "paper"
        self._client = TradingClient(
            api_key=config["api_key"],
            secret_key=config["secret_key"],
            paper=paper,
        )
        self._client.get_account()  # validate credentials
        self.status = "connected"

    def disconnect(self) -> None:
        self._client = None
        self.status = "disconnected"

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        if self._client is None:
            raise RuntimeError("Alpaca gateway not connected")
        # Delegate to TradeService which wraps alpaca-py
        svc = TradeService()
        svc._client = self._client  # reuse connected client
        order_id = svc.submit_order(symbol, action, qty)
        return OrderResult(
            status="submitted",
            order_id=order_id,
            qty=qty,
            price_estimate=None,
            reason=None,
        )
```

- [ ] **Step 4: Register AlpacaGateway in `api/services/gateway_manager.py`**

In `_register_gateways()`, uncomment and add:

```python
    from api.gateways.alpaca import AlpacaGateway
    _GATEWAY_CLASSES["alpaca"] = AlpacaGateway
```

- [ ] **Step 5: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_alpaca_gateway.py tests/test_gateway_manager.py -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/gateways/alpaca.py api/services/gateway_manager.py tests/test_alpaca_gateway.py
git commit -m "feat: AlpacaGateway adapter wrapping alpaca-py"
```

---

## Task 3: BinanceGateway adapter

**Files:**
- Modify: `requirements.txt` (add ccxt)
- Create: `api/gateways/binance.py`
- Modify: `api/services/gateway_manager.py` (register BinanceGateway)
- Test: `tests/test_binance_gateway.py`

### Background

BinanceGateway uses `ccxt` for Binance REST API. `connect()` creates a ccxt.binance exchange instance and calls `fetch_balance()` to validate credentials. `send_order()` calls `create_market_order()`.

- [ ] **Step 1: Add ccxt dependency**

Append to `requirements.txt`:

```
ccxt>=4.0.0
```

Install:

```bash
cd /Users/zakj/Documents/my/stock && pip install "ccxt>=4.0.0"
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_binance_gateway.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


def test_binance_connect_success():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        gw.connect({"api_key": "key", "api_secret": "secret"})
    assert gw.status == "connected"
    mock_exchange.fetch_balance.assert_called_once()


def test_binance_connect_failure():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    mock_exchange.fetch_balance.side_effect = Exception("Invalid API key")
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        with pytest.raises(Exception, match="Invalid API key"):
            gw.connect({"api_key": "bad", "api_secret": "bad"})


def test_binance_send_order():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    mock_exchange.create_market_order.return_value = {
        "id": "binance-ord-1",
        "price": 50000.0,
    }
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        gw.connect({"api_key": "key", "api_secret": "secret"})
    result = gw.send_order("BTC/USDT", "buy", 0.01)
    assert result.status == "submitted"
    assert result.order_id == "binance-ord-1"
    assert result.qty == 0.01
    mock_exchange.create_market_order.assert_called_once_with("BTC/USDT", "buy", 0.01)


def test_binance_disconnect():
    from api.gateways.binance import BinanceGateway
    gw = BinanceGateway()
    mock_exchange = MagicMock()
    with patch("api.gateways.binance.ccxt.binance", return_value=mock_exchange):
        gw.connect({"api_key": "key", "api_secret": "secret"})
    gw.disconnect()
    assert gw.status == "disconnected"
    assert gw._exchange is None
```

- [ ] **Step 3: Run tests to verify failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_binance_gateway.py -v 2>&1 | head -20
```

Expected: ImportError

- [ ] **Step 4: Create `api/gateways/binance.py`**

```python
import ccxt
from api.gateways.base import BaseGateway, OrderResult


class BinanceGateway(BaseGateway):
    name = "binance"
    label = "Binance"

    def __init__(self):
        self._exchange: ccxt.binance | None = None

    def connect(self, config: dict) -> None:
        self._exchange = ccxt.binance({
            "apiKey": config["api_key"],
            "secret": config["api_secret"],
        })
        self._exchange.fetch_balance()  # validate credentials
        self.status = "connected"

    def disconnect(self) -> None:
        self._exchange = None
        self.status = "disconnected"

    def send_order(self, symbol: str, action: str, qty: float) -> OrderResult:
        if self._exchange is None:
            raise RuntimeError("Binance gateway not connected")
        result = self._exchange.create_market_order(symbol, action.lower(), qty)
        return OrderResult(
            status="submitted",
            order_id=str(result.get("id")),
            qty=qty,
            price_estimate=result.get("price"),
            reason=None,
        )
```

- [ ] **Step 5: Register BinanceGateway in `api/services/gateway_manager.py`**

In `_register_gateways()`, add:

```python
    from api.gateways.binance import BinanceGateway
    _GATEWAY_CLASSES["binance"] = BinanceGateway
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_binance_gateway.py tests/test_gateway_manager.py -v
```

Expected: all PASSED

- [ ] **Step 7: Full suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add requirements.txt api/gateways/binance.py api/services/gateway_manager.py tests/test_binance_gateway.py
git commit -m "feat: BinanceGateway adapter using ccxt"
```

---

## Task 4: Gateway API routes

**Files:**
- Create: `api/routes/gateways.py`
- Modify: `api/main.py`
- Test: `tests/test_gateways_route.py`

### Background

5 new routes for gateway config management. Follow the same pattern as existing routes (e.g., `api/routes/confirmations.py`). The routes import `_manager` from `gateway_manager` and `DEFAULT_DB_PATH` from `db.schema`.

The `api/main.py` lifespan must be updated: `init_db()` → `_manager.load_from_db()` → `TradeService().sync_positions()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gateways_route.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_gateways_route.py -v 2>&1 | head -20
```

Expected: ImportError or 404 for `/gateways`

- [ ] **Step 3: Create `api/routes/gateways.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.services.gateway_manager import _manager
from db.schema import DEFAULT_DB_PATH

router = APIRouter()


class GatewayUpdateRequest(BaseModel):
    config: dict[str, str]
    enabled: bool


@router.get("/gateways")
def get_gateways():
    return _manager.get_all(DEFAULT_DB_PATH)


@router.put("/gateways/{name}")
def update_gateway(name: str, req: GatewayUpdateRequest):
    # Check gateway exists in DB
    all_gw = _manager.get_all(DEFAULT_DB_PATH)
    names = [g["name"] for g in all_gw]
    if name not in names:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    _manager.save_config(name, req.config, req.enabled, DEFAULT_DB_PATH)
    updated = _manager.get_all(DEFAULT_DB_PATH)
    return next(g for g in updated if g["name"] == name)


@router.post("/gateways/{name}/connect")
def connect_gateway(name: str):
    try:
        status = _manager.connect(name, DEFAULT_DB_PATH)
        return {"status": status}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/gateways/{name}/disconnect")
def disconnect_gateway(name: str):
    try:
        status = _manager.disconnect(name, DEFAULT_DB_PATH)
        return {"status": status}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/gateways/{name}/status")
def get_gateway_status(name: str):
    try:
        status = _manager.get_status(name)
        return {"name": name, "status": status}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
```

- [ ] **Step 4: Update `api/main.py`**

Register the new router and update lifespan. Read the current file first, then:

1. Add import: `from api.routes.gateways import router as gateways_router`
2. Add import: `from db.schema import init_db, DEFAULT_DB_PATH`
3. Add import: `from api.services.gateway_manager import _manager`
4. Update lifespan to:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB, load gateways, sync positions
    init_db(DEFAULT_DB_PATH)
    _manager.load_from_db(DEFAULT_DB_PATH)
    try:
        from api.services.trade_service import TradeService
        TradeService().sync_positions()
    except Exception:
        pass  # Alpaca creds not configured — skip sync
    yield
```

5. Add: `app.include_router(gateways_router)` after the existing router registrations.

- [ ] **Step 5: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_gateways_route.py -v
```

Expected: 12 PASSED

- [ ] **Step 6: Full suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/routes/gateways.py api/main.py tests/test_gateways_route.py
git commit -m "feat: GET/PUT/POST gateway API routes + lifespan init"
```

---

## Task 5: Migrate `POST /trade` to use GatewayManager

**Files:**
- Modify: `api/routes/trade.py`
- Modify: `tests/test_trade_route.py`

### Background

The existing `POST /trade` route at `api/routes/trade.py` calls `trade_svc.submit_order()` on line 94. We replace only that one call with `_manager.route_order()`. All other logic (RiskGate, Telegram confirmation, record_loss, _insert_pending) stays unchanged.

The existing tests mock `TradeService.return_value.submit_order`; we need to mock `_manager.route_order` instead for the confirmed-flow tests.

- [ ] **Step 1: Modify `api/routes/trade.py`**

Read the file first. Make these changes:

1. Add import at top: `from fastapi import APIRouter, HTTPException` (add HTTPException)
2. Add import at top: `from api.services.gateway_manager import _manager`
3. Add `gateway` field to `TradeRequest`:
   ```python
   class TradeRequest(BaseModel):
       symbol: str
       action: str
       size: float
       capital: float
       start: str
       end: str
       gateway: str = "alpaca"
   ```
4. In `post_trade()`, replace line 94:
   ```python
   alpaca_order_id = trade_svc.submit_order(req.symbol.upper(), req.action, qty)
   ```
   with:
   ```python
   try:
       gw_result = _manager.route_order(req.gateway, req.symbol.upper(), req.action, qty)
   except KeyError:
       raise HTTPException(status_code=400, detail=f"Unknown gateway: {req.gateway}")
   alpaca_order_id = gw_result.order_id
   ```

- [ ] **Step 2: Update `tests/test_trade_route.py`**

Two existing tests need `_manager` mock added. Replace `test_trade_returns_200` entirely with:

```python
def test_trade_returns_200():
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="ord-abc", qty=1.0, price_estimate=253.0, reason=None
        )
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code == 200
```

Replace `test_trade_confirmed_returns_submitted` entirely with:

```python
def test_trade_confirmed_returns_submitted():
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="ord-xyz", qty=1.0, price_estimate=253.0, reason=None
        )
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["order_id"] == "ord-xyz"
```

Add 3 new tests at the end of the file:

```python
def test_trade_default_gateway_uses_alpaca():
    """POST /trade without gateway field defaults to 'alpaca'."""
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="ord-default", qty=1.0, price_estimate=None, reason=None
        )
        resp = client.post("/trade", json=TRADE_BODY)  # no gateway field
    MockManager.route_order.assert_called_once()
    assert MockManager.route_order.call_args[0][0] == "alpaca"


def test_trade_with_binance_gateway():
    """POST /trade with gateway='binance' routes to Binance adapter."""
    from api.gateways.base import OrderResult
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        MockManager.route_order.return_value = OrderResult(
            status="submitted", order_id="binance-ord-1", qty=0.01, price_estimate=50000.0, reason=None
        )
        body = {**TRADE_BODY, "gateway": "binance"}
        resp = client.post("/trade", json=body)
    assert resp.json()["status"] == "submitted"
    assert resp.json()["order_id"] == "binance-ord-1"
    MockManager.route_order.assert_called_once()
    assert MockManager.route_order.call_args[0][0] == "binance"


def test_trade_unknown_gateway_returns_400():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade._manager") as MockManager, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        MockManager.route_order.side_effect = KeyError("Unknown gateway: bogus")
        body = {**TRADE_BODY, "gateway": "bogus"}
        resp = client.post("/trade", json=body)
    assert resp.status_code == 400
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_trade_route.py -v
```

Expected: all PASSED (original 7 + 3 new = 10)

- [ ] **Step 4: Full suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/routes/trade.py tests/test_trade_route.py
git commit -m "feat: POST /trade routes through GatewayManager (backward-compatible)"
```

---

## Task 6: Frontend — types, API functions, sidebar

**Files:**
- Modify: `web/lib/types.ts`
- Modify: `web/lib/api.ts`
- Modify: `web/components/layout/Sidebar.tsx`

### Background

Add the TypeScript interface and API functions needed by the settings page. Also add "设置" to the sidebar nav. This task does not create the settings page yet — just the data layer and navigation.

- [ ] **Step 1: Add `GatewayConfig` to `web/lib/types.ts`**

Append after the existing `ApiLogEntry` interface:

```typescript
export interface GatewayConfig {
  name: string;
  label: string;
  enabled: boolean;
  status: "connected" | "disconnected" | "error";
  config: Record<string, string>;
}
```

- [ ] **Step 2: Add gateway API functions to `web/lib/api.ts`**

Add import of `GatewayConfig` to the existing import statement, then append 5 functions:

```typescript
export async function fetchGateways(): Promise<GatewayConfig[]> {
  return apiFetch<GatewayConfig[]>("/gateways");
}

export async function saveGateway(
  name: string,
  config: Record<string, string>,
  enabled: boolean
): Promise<GatewayConfig> {
  return apiFetch<GatewayConfig>(`/gateways/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config, enabled }),
  });
}

export async function connectGateway(
  name: string
): Promise<{ status: string; detail?: string }> {
  return apiFetch<{ status: string; detail?: string }>(
    `/gateways/${name}/connect`,
    { method: "POST" }
  );
}

export async function disconnectGateway(
  name: string
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/gateways/${name}/disconnect`, {
    method: "POST",
  });
}

export async function fetchGatewayStatus(
  name: string
): Promise<{ name: string; status: string }> {
  return apiFetch<{ name: string; status: string }>(
    `/gateways/${name}/status`
  );
}
```

- [ ] **Step 3: Add "设置" to sidebar nav**

In `web/components/layout/Sidebar.tsx`, add to the `navItems` array:

```typescript
const navItems = [
  { href: "/live",       label: "实盘" },
  { href: "/strategies", label: "策略库" },
  { href: "/terminal",   label: "交易终端" },
  { href: "/explore",    label: "数据探索" },
  { href: "/messages",   label: "消息中心" },
  { href: "/settings",   label: "设置" },
];
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/zakj/Documents/my/stock/web && npx next build 2>&1 | tail -10
```

Expected: Build succeeds (new types/functions compile; `/settings` route doesn't exist yet but nav link is fine)

- [ ] **Step 5: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/lib/types.ts web/lib/api.ts web/components/layout/Sidebar.tsx
git commit -m "feat: gateway TypeScript types, API functions, sidebar nav"
```

---

## Task 7: Frontend — Settings page with GatewayList + GatewayDetail

**Files:**
- Create: `web/app/settings/page.tsx`
- Create: `web/components/settings/GatewayList.tsx`
- Create: `web/components/settings/GatewayDetail.tsx`

### Background

The settings page uses a sidebar + detail panel layout. Left side lists all 4 gateways with status dots. Right side shows the config form for the selected gateway. Each gateway has different fields.

Follow existing component patterns: `"use client"`, `useState`/`useEffect`, shadcn/ui `Button`/`Input`/`Label`/`Select` components, `useToast` for notifications.

- [ ] **Step 1: Create `web/components/settings/GatewayList.tsx`**

```typescript
"use client";
import type { GatewayConfig } from "@/lib/types";

const statusColor: Record<string, string> = {
  connected: "bg-green-500",
  disconnected: "bg-zinc-500",
  error: "bg-red-500",
};

interface Props {
  gateways: GatewayConfig[];
  selected: string | null;
  onSelect: (name: string) => void;
}

export function GatewayList({ gateways, selected, onSelect }: Props) {
  return (
    <div className="flex flex-col gap-1 w-[160px] border-r pr-4">
      <h3 className="text-xs font-medium text-muted-foreground mb-2 uppercase tracking-wide">
        交易接口
      </h3>
      {gateways.map((gw) => (
        <button
          key={gw.name}
          onClick={() => onSelect(gw.name)}
          className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors text-left ${
            selected === gw.name
              ? "bg-accent text-accent-foreground font-medium"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          }`}
        >
          <span
            className={`h-2 w-2 rounded-full flex-shrink-0 ${statusColor[gw.status] ?? "bg-zinc-500"}`}
          />
          {gw.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `web/components/settings/GatewayDetail.tsx`**

```typescript
"use client";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { saveGateway, connectGateway, disconnectGateway } from "@/lib/api";
import { useToast } from "@/components/ui/use-toast";
import type { GatewayConfig } from "@/lib/types";

interface FieldDef {
  key: string;
  label: string;
  type: "text" | "password" | "select";
  options?: string[];
  placeholder?: string;
}

const GATEWAY_FIELDS: Record<string, FieldDef[]> = {
  alpaca: [
    { key: "api_key", label: "API Key", type: "text" },
    { key: "secret_key", label: "Secret Key", type: "password", placeholder: "已保存，输入新值可更新" },
    { key: "mode", label: "模式", type: "select", options: ["paper", "live"] },
  ],
  binance: [
    { key: "api_key", label: "API Key", type: "text" },
    { key: "api_secret", label: "API Secret", type: "password", placeholder: "已保存，输入新值可更新" },
  ],
  futu: [
    { key: "host", label: "Host", type: "text", placeholder: "127.0.0.1" },
    { key: "port", label: "Port", type: "text", placeholder: "11111" },
  ],
  ib: [
    { key: "host", label: "Host", type: "text", placeholder: "127.0.0.1" },
    { key: "port", label: "Port", type: "text", placeholder: "7497" },
  ],
};

const STUB_GATEWAYS = new Set(["futu", "ib"]);
const STUB_MESSAGES: Record<string, string> = {
  futu: "需先在本地运行 FutuOpenD 程序（默认端口 11111）",
  ib: "需先在本地运行 TWS 或 IB Gateway 程序（默认端口 7497）",
};

interface Props {
  gateway: GatewayConfig;
  onUpdated: () => void;
}

export function GatewayDetail({ gateway, onUpdated }: Props) {
  const { toast } = useToast();
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initial: Record<string, string> = {};
    const fields = GATEWAY_FIELDS[gateway.name] ?? [];
    for (const f of fields) {
      const val = gateway.config[f.key];
      initial[f.key] = val && val !== "***" ? val : "";
    }
    setForm(initial);
    setError(null);
  }, [gateway.name, gateway.config]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const config: Record<string, string> = {};
      for (const [k, v] of Object.entries(form)) {
        if (v) config[k] = v;
      }
      await saveGateway(gateway.name, config, true);
      toast({ description: "配置已保存" });
      onUpdated();
    } catch (err) {
      toast({ description: `保存失败: ${err}`, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      const res = await connectGateway(gateway.name);
      if (res.status === "error") {
        setError(res.detail ?? "连接失败");
      }
      onUpdated();
    } catch (err) {
      setError(String(err));
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      await disconnectGateway(gateway.name);
      onUpdated();
    } catch (err) {
      setError(String(err));
    } finally {
      setConnecting(false);
    }
  };

  const fields = GATEWAY_FIELDS[gateway.name] ?? [];

  return (
    <div className="flex-1 pl-6 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">{gateway.label}</h2>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${
            gateway.status === "connected"
              ? "bg-green-900/50 text-green-400"
              : gateway.status === "error"
                ? "bg-red-900/50 text-red-400"
                : "bg-zinc-800 text-zinc-400"
          }`}
        >
          {gateway.status === "connected" ? "已连接" : gateway.status === "error" ? "错误" : "未连接"}
        </span>
      </div>

      {STUB_GATEWAYS.has(gateway.name) && (
        <p className="text-sm text-amber-500 bg-amber-950/30 rounded-md px-3 py-2">
          {STUB_MESSAGES[gateway.name]}
        </p>
      )}

      <div className="space-y-3 max-w-sm">
        {fields.map((f) =>
          f.type === "select" ? (
            <div key={f.key} className="flex flex-col gap-1">
              <Label>{f.label}</Label>
              <Select value={form[f.key] || f.options?.[0] || ""} onValueChange={(v) => setForm({ ...form, [f.key]: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {f.options?.map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div key={f.key} className="flex flex-col gap-1">
              <Label>{f.label}</Label>
              <Input
                type={f.type === "password" ? "password" : "text"}
                placeholder={f.placeholder}
                value={form[f.key] || ""}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
              />
            </div>
          )
        )}
      </div>

      <div className="flex gap-2 max-w-sm">
        <Button onClick={handleSave} disabled={saving} variant="outline" className="flex-1">
          {saving ? "保存中..." : "保存"}
        </Button>
        {gateway.status === "connected" ? (
          <Button onClick={handleDisconnect} disabled={connecting} variant="destructive" className="flex-1">
            {connecting ? "断开中..." : "断开"}
          </Button>
        ) : (
          <Button onClick={handleConnect} disabled={connecting} className="flex-1">
            {connecting ? "连接中..." : "连接"}
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 3: Create `web/app/settings/page.tsx`**

```typescript
"use client";
import { useEffect, useState } from "react";
import { fetchGateways } from "@/lib/api";
import { GatewayList } from "@/components/settings/GatewayList";
import { GatewayDetail } from "@/components/settings/GatewayDetail";
import type { GatewayConfig } from "@/lib/types";

export default function SettingsPage() {
  const [gateways, setGateways] = useState<GatewayConfig[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const data = await fetchGateways();
      setGateways(data);
      if (!selected && data.length > 0) setSelected(data[0].name);
    } catch {
      // API offline — show empty state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const selectedGateway = gateways.find((g) => g.name === selected);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">设置</h1>
        <div className="flex gap-6">
          <div className="w-[160px] space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-9 rounded-md bg-accent animate-pulse" />
            ))}
          </div>
          <div className="flex-1 space-y-3">
            <div className="h-8 w-48 rounded bg-accent animate-pulse" />
            <div className="h-10 w-80 rounded bg-accent animate-pulse" />
            <div className="h-10 w-80 rounded bg-accent animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>
      <div className="flex">
        <GatewayList gateways={gateways} selected={selected} onSelect={setSelected} />
        {selectedGateway ? (
          <GatewayDetail gateway={selectedGateway} onUpdated={load} />
        ) : (
          <div className="flex-1 pl-6 text-muted-foreground">选择一个交易接口</div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/zakj/Documents/my/stock/web && npx next build 2>&1 | tail -10
```

Expected: Build succeeds

- [ ] **Step 5: Full backend test suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add web/app/settings/ web/components/settings/
git commit -m "feat: /settings page with gateway list + detail panel"
```

---

## Completion Criteria

- [ ] `python -m pytest tests/ -q` → all passed (existing + ~30 new tests)
- [ ] `cd web && npx next build` → success
- [ ] `curl http://localhost:8000/gateways` returns JSON array of 4 gateways
- [ ] Frontend `/settings` page shows gateway list with config forms
