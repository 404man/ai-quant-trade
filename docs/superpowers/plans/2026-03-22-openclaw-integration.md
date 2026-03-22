# OpenClaw Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the AI quant trading system with OpenClaw bidirectionally — Skills for querying, Webhooks for pushing events.

**Architecture:** Bearer Token auth on all FastAPI routes. 4 OpenClaw Skills (SKILL.md + curl) for querying backtest/sentiment/signal/positions. WebhookService pushes events (signals, risk alerts, order status, daily summary) to OpenClaw's `/hooks/agent` endpoint. New `/positions` and `/daily-summary` endpoints added.

**Tech Stack:** FastAPI, httpx (already in deps), OpenClaw Skills (SKILL.md files)

**Spec:** `docs/superpowers/specs/2026-03-22-openclaw-integration-design.md`

---

## File Structure

### New files

| File | Responsibility |
|------|---------------|
| `api/auth.py` | Bearer Token auth dependency (`verify_api_key`) |
| `api/routes/positions.py` | `GET /positions` — returns current positions from local DB |
| `api/routes/daily_summary.py` | `POST /daily-summary` — triggers daily summary push to OpenClaw |
| `api/services/webhook_service.py` | Pushes events to OpenClaw `/hooks/agent` via httpx |
| `openclaw/skills/stock_backtest/SKILL.md` | Skill: backtest query |
| `openclaw/skills/stock_sentiment/SKILL.md` | Skill: sentiment query |
| `openclaw/skills/stock_signal/SKILL.md` | Skill: signal query |
| `openclaw/skills/stock_positions/SKILL.md` | Skill: positions query |
| `tests/test_auth.py` | Auth tests |
| `tests/test_positions_route.py` | Positions endpoint tests |
| `tests/test_webhook_service.py` | WebhookService tests |
| `tests/test_daily_summary_route.py` | Daily summary endpoint tests |

### Modified files

| File | Change |
|------|--------|
| `api/main.py:1-41` | Global auth dependency + register positions/daily_summary routers |
| `api/services/trade_service.py:49-55` | Add `get_positions()` method after `get_position_count()` |
| `api/routes/signal.py:44-49` | Add webhook push after response build |
| `api/routes/trade.py:80-107` | Add webhook push for risk blocks + order outcomes |
| `.env.example:1-18` | Add OPENCLAW_HOOK_URL, OPENCLAW_HOOK_TOKEN |

---

### Task 1: Bearer Token Authentication

**Files:**
- Create: `api/auth.py`
- Create: `tests/test_auth.py`
- Modify: `api/main.py:1-41`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_no_auth_required():
    """GET /health works without any auth header, even when LOCAL_API_KEY is set."""
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_valid_token_allows_request():
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/backtest", params={"symbol": "AAPL", "strategy": "rsi", "start": "2020-01-01", "end": "2024-12-31"},
                          headers={"Authorization": "Bearer secret123"})
    # May be 404 (no data) or 200, but NOT 401
    assert resp.status_code != 401


def test_wrong_token_returns_401():
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/backtest", params={"symbol": "AAPL", "strategy": "rsi", "start": "2020-01-01", "end": "2024-12-31"},
                          headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_missing_header_returns_401():
    with patch.dict(os.environ, {"LOCAL_API_KEY": "secret123"}):
        resp = client.get("/backtest", params={"symbol": "AAPL", "strategy": "rsi", "start": "2020-01-01", "end": "2024-12-31"})
    assert resp.status_code == 401


def test_no_api_key_env_skips_auth():
    """When LOCAL_API_KEY is not set, all requests pass without auth."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("LOCAL_API_KEY", None)
        resp = client.get("/health")
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_auth.py -v`
Expected: Some tests FAIL (no auth is enforced yet, so wrong token still succeeds)

- [ ] **Step 3: Implement api/auth.py**

```python
# api/auth.py
import os
from fastapi import HTTPException, Request


def verify_api_key(request: Request):
    """FastAPI dependency: validate Bearer token against LOCAL_API_KEY env var.

    Skips auth when LOCAL_API_KEY is not set (dev mode).
    """
    api_key = os.environ.get("LOCAL_API_KEY")
    if not api_key:
        return  # dev mode: no auth
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {api_key}":
        raise HTTPException(status_code=401, detail="Invalid API key")
```

- [ ] **Step 4: Update api/main.py to add global auth + exclude /health**

Replace the entire `api/main.py` with:

```python
# api/main.py
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from api.auth import verify_api_key
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router
from api.routes.sentiment import router as sentiment_router
from api.routes.signal import router as signal_router
from api.routes.trade import router as trade_router
from api.routes.confirmations import router as confirmations_router
from api.routes.gateways import router as gateways_router
from db.schema import init_db, DEFAULT_DB_PATH
from api.services.gateway_manager import _manager


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


app = FastAPI(
    title="AI Quant System",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(verify_api_key)],
)

app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(sentiment_router)
app.include_router(signal_router)
app.include_router(trade_router)
app.include_router(confirmations_router)
app.include_router(gateways_router)


@app.get("/health", dependencies=[])
def health():
    """Health check — no auth required. Empty dependencies=[] overrides global auth."""
    return {"status": "ok"}
```

Key change: `dependencies=[Depends(verify_api_key)]` on the app, and `dependencies=[]` on `/health` to override.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_auth.py -v`
Expected: 5 PASSED

- [ ] **Step 6: Run full test suite to verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: All existing tests still pass (they don't set LOCAL_API_KEY, so auth is skipped)

- [ ] **Step 7: Commit**

```bash
git add api/auth.py tests/test_auth.py api/main.py
git commit -m "feat: add Bearer Token auth to all API routes (health excluded)"
```

---

### Task 2: GET /positions Endpoint + TradeService.get_positions()

**Files:**
- Modify: `api/services/trade_service.py:49-55`
- Create: `api/routes/positions.py`
- Create: `tests/test_positions_route.py`
- Modify: `api/main.py` (register router)

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_positions_route.py -v`
Expected: FAIL — module `api.routes.positions` not found

- [ ] **Step 3: Add get_positions() to TradeService**

In `api/services/trade_service.py`, add after `get_position_count()` (after line 55):

```python
    def get_positions(self) -> list[dict]:
        """Return all open positions from local DB."""
        conn = get_connection(self.db_path)
        try:
            rows = conn.execute(
                "SELECT symbol, qty, avg_entry_price, side FROM positions"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
```

- [ ] **Step 4: Create api/routes/positions.py**

```python
# api/routes/positions.py
from fastapi import APIRouter
from api.services.trade_service import TradeService

router = APIRouter()


@router.get("/positions")
def get_positions():
    trade_svc = TradeService()
    positions = trade_svc.get_positions()
    return {
        "positions": positions,
        "count": len(positions),
    }
```

- [ ] **Step 5: Register router in api/main.py**

Add import after gateways_router import:
```python
from api.routes.positions import router as positions_router
```

Add after `app.include_router(gateways_router)`:
```python
app.include_router(positions_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_positions_route.py -v`
Expected: 2 PASSED

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add api/services/trade_service.py api/routes/positions.py tests/test_positions_route.py api/main.py
git commit -m "feat: add GET /positions endpoint + TradeService.get_positions()"
```

---

### Task 3: WebhookService

**Files:**
- Create: `api/services/webhook_service.py`
- Create: `tests/test_webhook_service.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_webhook_service.py
import os
import pytest
from unittest.mock import patch, MagicMock


def test_push_calls_httpx_post():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    with patch("api.services.webhook_service.httpx") as mock_httpx:
        svc.push("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})
    mock_httpx.post.assert_called_once()
    call_kwargs = mock_httpx.post.call_args
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer tok123"
    payload = call_kwargs[1]["json"]
    assert payload["name"] == "stock-signal"
    assert "AAPL" in payload["message"]


def test_push_silent_on_failure():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    with patch("api.services.webhook_service.httpx") as mock_httpx:
        mock_httpx.post.side_effect = Exception("connection refused")
        # Should not raise
        svc.push("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})


def test_push_skips_when_not_configured():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("OPENCLAW_HOOK_URL", None)
        os.environ.pop("OPENCLAW_HOOK_TOKEN", None)
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    with patch("api.services.webhook_service.httpx") as mock_httpx:
        svc.push("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})
    mock_httpx.post.assert_not_called()


def test_format_signal_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("signal", {"symbol": "AAPL", "action": "buy", "size": 0.05, "score": 0.78})
    assert "AAPL" in msg
    assert "buy" in msg.lower() or "买" in msg


def test_format_risk_alert_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("risk_alert", {"symbol": "AAPL", "reason": "Daily loss limit reached"})
    assert "AAPL" in msg
    assert "Daily loss limit reached" in msg or "风控" in msg


def test_format_order_status_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("order_status", {"symbol": "AAPL", "action": "buy", "status": "submitted", "qty": 5, "price_estimate": 178.5, "order_id": "abc123"})
    assert "AAPL" in msg
    assert "5" in msg


def test_format_daily_summary_message():
    with patch.dict(os.environ, {"OPENCLAW_HOOK_URL": "http://localhost:18789/hooks/agent", "OPENCLAW_HOOK_TOKEN": "tok123"}):
        from api.services.webhook_service import WebhookService
        svc = WebhookService()
    msg = svc._format_message("daily_summary", {
        "positions": [{"symbol": "AAPL", "qty": 5, "side": "long", "avg_entry_price": 178.5}],
        "daily_pnl": -12.5,
        "account_balance": 487.5,
        "date": "2026-03-22",
    })
    assert "AAPL" in msg
    assert "2026-03-22" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_webhook_service.py -v`
Expected: FAIL — module `api.services.webhook_service` not found

- [ ] **Step 3: Implement WebhookService**

```python
# api/services/webhook_service.py
import logging
import os

import httpx

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(self):
        self.url = os.environ.get("OPENCLAW_HOOK_URL", "")
        self.token = os.environ.get("OPENCLAW_HOOK_TOKEN", "")

    def push(self, event_type: str, data: dict) -> None:
        """Push an event to OpenClaw webhook. Fails silently."""
        if not self.url or not self.token:
            return
        message = self._format_message(event_type, data)
        try:
            httpx.post(
                self.url,
                json={"message": message, "name": f"stock-{event_type}"},
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5.0,
            )
        except Exception as e:
            logger.warning("Webhook push failed: %s", e)

    def _format_message(self, event_type: str, data: dict) -> str:
        formatters = {
            "signal": self._fmt_signal,
            "risk_alert": self._fmt_risk_alert,
            "order_status": self._fmt_order_status,
            "daily_summary": self._fmt_daily_summary,
        }
        fmt = formatters.get(event_type)
        return fmt(data) if fmt else str(data)

    def _fmt_signal(self, d: dict) -> str:
        action_zh = "买入" if d["action"] == "buy" else "卖出"
        pct = round(d["size"] * 100, 1)
        return f"交易信号：{d['symbol']} {action_zh}，仓位 {pct}%，评分 {d['score']}"

    def _fmt_risk_alert(self, d: dict) -> str:
        return f"风控警报：{d['symbol']} 交易被拦截 — {d['reason']}"

    def _fmt_order_status(self, d: dict) -> str:
        if d["status"] == "submitted":
            action_zh = "买入" if d["action"] == "buy" else "卖出"
            return f"订单成交：{d['symbol']} {action_zh} {d['qty']} 股 @ ${d['price_estimate']}"
        reason = d.get("reason", d["status"])
        return f"订单取消：{d['symbol']} — {reason}"

    def _fmt_daily_summary(self, d: dict) -> str:
        lines = [f"每日摘要 ({d['date']})"]
        if d.get("account_balance") is not None:
            lines.append(f"账户余额: ${d['account_balance']:.2f}")
        lines.append(f"当日盈亏: ${d['daily_pnl']:.2f}")
        if d["positions"]:
            lines.append("持仓:")
            for p in d["positions"]:
                lines.append(f"  {p['symbol']} {p['qty']}股 {p['side']} @ ${p['avg_entry_price']}")
        else:
            lines.append("持仓: 空仓")
        return "\n".join(lines)
```

- [ ] **Step 4: Update .env.example**

Append to `.env.example`:

```
# OpenClaw Webhook
OPENCLAW_HOOK_URL=http://127.0.0.1:18789/hooks/agent
OPENCLAW_HOOK_TOKEN=your_hook_token_here
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_webhook_service.py -v`
Expected: 7 PASSED

- [ ] **Step 6: Commit**

```bash
git add api/services/webhook_service.py tests/test_webhook_service.py .env.example
git commit -m "feat: add WebhookService for OpenClaw event push"
```

---

### Task 4: Webhook Triggers in Signal + Trade Routes

**Files:**
- Modify: `api/routes/signal.py:44-49`
- Modify: `api/routes/trade.py:80-107`

- [ ] **Step 1: Add webhook push to signal route**

In `api/routes/signal.py`, add import at top:
```python
from api.services.webhook_service import WebhookService
```

Replace the `return` statement (current lines 44-49):

```python
    response = {
        "symbol": symbol.upper(),
        **signal,
        "risk_blocked": risk_blocked,
        "risk_reason": risk_reason,
    }

    # Push signal webhook if actionable (buy/sell, not blocked to hold)
    if response["action"] in ("buy", "sell"):
        WebhookService().push("signal", {
            "symbol": response["symbol"],
            "action": response["action"],
            "size": response["size"],
            "score": response["score"],
        })

    return response
```

- [ ] **Step 2: Add webhook pushes to trade route**

In `api/routes/trade.py`, add import at top:
```python
from api.services.webhook_service import WebhookService
```

After the risk block return (current line 81 `return {"status": "blocked", ...}`), add webhook push before the return:

```python
    if not risk_result.allowed:
        WebhookService().push("risk_alert", {
            "symbol": req.symbol.upper(),
            "reason": risk_result.reason,
            "capital": req.capital,
            "daily_loss": daily_loss,
        })
        return {"status": "blocked", "reason": risk_result.reason}
```

After the successful submission (current line 103), add webhook push before the return:

```python
        alpaca_order_id = gw_result.order_id
        trade_svc.record_loss(today, 0.0)
        WebhookService().push("order_status", {
            "order_id": alpaca_order_id,
            "symbol": req.symbol.upper(),
            "action": req.action,
            "status": "submitted",
            "qty": qty,
            "price_estimate": last_price,
        })
        return {"status": "submitted", "order_id": alpaca_order_id, "qty": qty, "price_estimate": last_price}
```

After the cancellation (current line 107), add webhook push before the return:

```python
    reason = "user_rejected" if outcome == "cancelled" else "timeout"
    send_cancellation_notice(order_id=order_id, symbol=req.symbol.upper(), reason=reason)
    WebhookService().push("order_status", {
        "order_id": order_id,
        "symbol": req.symbol.upper(),
        "action": req.action,
        "status": "cancelled",
        "qty": qty,
        "price_estimate": last_price,
        "reason": reason,
    })
    return {"status": "cancelled", "reason": reason}
```

- [ ] **Step 3: Run full test suite to verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: All tests pass. WebhookService silently no-ops when env vars are not set, so existing tests are unaffected.

- [ ] **Step 4: Commit**

```bash
git add api/routes/signal.py api/routes/trade.py
git commit -m "feat: add webhook triggers for signal, risk alert, and order status"
```

---

### Task 5: POST /daily-summary Endpoint

**Files:**
- Create: `api/routes/daily_summary.py`
- Create: `tests/test_daily_summary_route.py`
- Modify: `api/main.py` (register router)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_daily_summary_route.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)


def test_daily_summary_triggers_webhook():
    mock_trade_svc = MagicMock()
    mock_trade_svc.get_positions.return_value = [
        {"symbol": "AAPL", "qty": 5, "avg_entry_price": 178.5, "side": "long"}
    ]
    mock_trade_svc.get_daily_loss.return_value = 12.5
    mock_trade_svc._get_client.side_effect = Exception("no creds")

    with patch("api.routes.daily_summary.TradeService", return_value=mock_trade_svc), \
         patch("api.routes.daily_summary.WebhookService") as MockWH:
        mock_wh_instance = MockWH.return_value
        resp = client.post("/daily-summary")

    assert resp.status_code == 200
    assert resp.json() == {"status": "sent"}
    mock_wh_instance.push.assert_called_once()
    call_args = mock_wh_instance.push.call_args
    assert call_args[0][0] == "daily_summary"
    data = call_args[0][1]
    assert data["daily_pnl"] == -12.5
    assert data["account_balance"] is None  # Alpaca unavailable
    assert len(data["positions"]) == 1


def test_daily_summary_with_balance():
    mock_trade_svc = MagicMock()
    mock_trade_svc.get_positions.return_value = []
    mock_trade_svc.get_daily_loss.return_value = 0.0
    mock_account = MagicMock()
    mock_account.equity = "500.00"
    mock_trade_svc._get_client.return_value.get_account.return_value = mock_account

    with patch("api.routes.daily_summary.TradeService", return_value=mock_trade_svc), \
         patch("api.routes.daily_summary.WebhookService") as MockWH:
        mock_wh_instance = MockWH.return_value
        resp = client.post("/daily-summary")

    assert resp.status_code == 200
    data = mock_wh_instance.push.call_args[0][1]
    assert data["account_balance"] == 500.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_daily_summary_route.py -v`
Expected: FAIL — module `api.routes.daily_summary` not found

- [ ] **Step 3: Implement daily_summary route**

```python
# api/routes/daily_summary.py
from datetime import date

from fastapi import APIRouter

from api.services.trade_service import TradeService
from api.services.webhook_service import WebhookService

router = APIRouter()


@router.post("/daily-summary")
def post_daily_summary():
    trade_svc = TradeService()
    positions = trade_svc.get_positions()
    daily_loss = trade_svc.get_daily_loss(date.today().isoformat())

    account_balance = None
    try:
        account = trade_svc._get_client().get_account()
        account_balance = float(account.equity)
    except Exception:
        pass

    WebhookService().push("daily_summary", {
        "positions": positions,
        "daily_pnl": -daily_loss,
        "account_balance": account_balance,
        "date": date.today().isoformat(),
    })
    return {"status": "sent"}
```

- [ ] **Step 4: Register router in api/main.py**

Add import:
```python
from api.routes.daily_summary import router as daily_summary_router
```

Add after positions_router:
```python
app.include_router(daily_summary_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_daily_summary_route.py -v`
Expected: 2 PASSED

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add api/routes/daily_summary.py tests/test_daily_summary_route.py api/main.py
git commit -m "feat: add POST /daily-summary endpoint for OpenClaw push"
```

---

### Task 6: OpenClaw Skills (4 SKILL.md files)

**Files:**
- Create: `openclaw/skills/stock_backtest/SKILL.md`
- Create: `openclaw/skills/stock_sentiment/SKILL.md`
- Create: `openclaw/skills/stock_signal/SKILL.md`
- Create: `openclaw/skills/stock_positions/SKILL.md`

- [ ] **Step 1: Create stock_backtest skill**

```markdown
---
name: stock_backtest
description: Query stock backtesting results (Sharpe, drawdown, returns) from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Backtest

When the user asks to backtest a stock (e.g. "回测 AAPL", "backtest TSLA rsi", "回测 MSFT ma交叉"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker, e.g. AAPL, TSLA, MSFT
   - `strategy` (optional): `rsi` (RSI均值回归) or `ma_crossover` (MA双线交叉). Default: `rsi`
   - `start` (optional): Start date YYYY-MM-DD. Default: `2020-01-01`
   - `end` (optional): End date YYYY-MM-DD. Default: `2024-12-31`

2. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/backtest?symbol={SYMBOL}&strategy={STRATEGY}&start={START}&end={END}"
   ```

3. **Interpret the response:**
   The JSON response contains:
   - `sharpe_ratio`: Risk-adjusted return (> 1.0 is good, > 2.0 is excellent)
   - `max_drawdown`: Worst peak-to-trough loss (e.g. -0.15 = -15%)
   - `annual_return`: Annualized return (e.g. 0.12 = 12%)
   - `total_trades`: Number of trades executed
   - `win_rate`: Percentage of profitable trades

   Present results in a clear summary, e.g.:
   "AAPL RSI策略回测 (2020-2024): Sharpe 1.32, 年化收益 15.2%, 最大回撤 -12.3%, 共62笔交易, 胜率 58%"

4. **Error handling:**
   - 404: No price data available for this symbol
   - 400: Invalid strategy name (only `rsi` or `ma_crossover` supported)
```

- [ ] **Step 2: Create stock_sentiment skill**

```markdown
---
name: stock_sentiment
description: Query AI sentiment analysis for a stock from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Sentiment

When the user asks about stock sentiment (e.g. "情绪 TSLA", "sentiment AAPL", "MSFT市场情绪"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker

2. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/sentiment?symbol={SYMBOL}"
   ```

3. **Interpret the response:**
   The JSON response contains:
   - `sentiment`: One of `bullish` (看涨), `bearish` (看跌), `neutral` (中性)
   - `confidence`: 0.0 to 1.0 confidence score

   Present in natural language, e.g.:
   "TSLA 当前市场情绪: 看涨 (置信度 72%)"

4. **Error handling:**
   - If confidence is below 0.5, note that the signal is weak
   - If sentiment is neutral, mention it may be due to limited recent news
```

- [ ] **Step 3: Create stock_signal skill**

```markdown
---
name: stock_signal
description: Get current trading signal (buy/sell/hold) for a stock from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Signal

When the user asks for a trading signal (e.g. "信号 AAPL", "signal TSLA", "MSFT能买吗"):

1. **Extract parameters:**
   - `symbol` (required): Stock ticker
   - `capital` (optional): Portfolio capital in USD. Default: 500

2. **Compute date range:**
   - `start`: 30 calendar days before today (YYYY-MM-DD)
   - `end`: today (YYYY-MM-DD)

3. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/signal?symbol={SYMBOL}&start={START}&end={END}&capital={CAPITAL}"
   ```

4. **Interpret the response:**
   The JSON response contains:
   - `action`: `buy` (买入), `sell` (卖出), or `hold` (持有)
   - `size`: Position size as fraction (e.g. 0.05 = 5% of capital)
   - `score`: Composite signal score (-1.0 to 1.0)
   - `risk_blocked`: Whether risk controls blocked the trade
   - `risk_reason`: Why risk controls blocked (if applicable)

   Present in natural language, e.g.:
   "AAPL 信号: 买入，建议仓位 5%，综合评分 0.78"
   or if blocked:
   "AAPL 原始信号为买入，但被风控拦截: 单日亏损已达限额"

5. **Error handling:**
   - 404: No price data for this symbol/date range
```

- [ ] **Step 4: Create stock_positions skill**

```markdown
---
name: stock_positions
description: Query current portfolio positions and account status from the AI quant trading system
metadata: {"openclaw":{"requires":{"env":["LOCAL_API_KEY"]}}}
---

# Stock Positions

When the user asks about positions or account status (e.g. "持仓", "positions", "账户状态", "我现在有什么股票"):

1. **Call the API:**
   ```
   exec curl -s -H "Authorization: Bearer $LOCAL_API_KEY" \
     "http://127.0.0.1:8000/positions"
   ```

2. **Interpret the response:**
   The JSON response contains:
   - `positions`: Array of position objects, each with:
     - `symbol`: Stock ticker
     - `qty`: Number of shares
     - `avg_entry_price`: Average entry price
     - `side`: Position direction (long/short)
   - `count`: Total number of open positions

   Present as a formatted summary, e.g.:
   "当前持仓 (2个):
    - AAPL: 5股 多头 @ $178.50
    - TSLA: 3股 多头 @ $245.00"

   If no positions:
   "当前空仓，没有持仓。"
```

- [ ] **Step 5: Verify skill files exist and are valid**

Run: `ls -la openclaw/skills/*/SKILL.md`
Expected: 4 SKILL.md files listed

- [ ] **Step 6: Commit**

```bash
git add openclaw/
git commit -m "feat: add 4 OpenClaw Skills for backtest, sentiment, signal, positions"
```

---

### Task 7: Integration Smoke Test

**Files:**
- No new files — verification only

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (existing + new tests from Tasks 1-5)

- [ ] **Step 2: Verify FastAPI starts**

Run: `timeout 5 python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 2>&1 || true`
Expected: "Application startup complete" appears (it will timeout after 5s, that's fine)

- [ ] **Step 3: Verify OpenClaw can discover skills (if openclaw is available)**

Run: `ls openclaw/skills/*/SKILL.md | wc -l`
Expected: `4`

- [ ] **Step 4: Test auth works end-to-end**

Run (in a separate terminal with the server running, or via TestClient):
```bash
# Without auth — should fail
curl -s http://127.0.0.1:8000/positions
# With auth — should succeed (after setting LOCAL_API_KEY)
curl -s -H "Authorization: Bearer $LOCAL_API_KEY" http://127.0.0.1:8000/positions
```

- [ ] **Step 5: Final commit if any adjustments needed**

If any fixes were needed during smoke test, commit them.
