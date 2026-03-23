# Phase 4: Alpaca Paper Trading + Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Alpaca paper trading and a Telegram bot so that every buy/sell signal triggers a Telegram confirmation message, and a `YES` reply within 5 minutes submits the order to Alpaca; timeout or `NO` cancels it silently with a notification.

**Architecture:** Three layers — `TradeService` wraps the Alpaca SDK and manages order lifecycle; the Telegram bot runs as a long-polling subprocess and writes pending confirmations to SQLite; `POST /trade` ties them together with the RiskGate already built in Phase 3. Daily loss reset runs at startup and is persisted to SQLite across restarts.

**Tech Stack:** Python 3.11, FastAPI, `alpaca-py` (Alpaca official SDK), `python-telegram-bot>=20.0` (async), SQLite (via existing `db/schema.py`), `pytest` with all mocks

---

## Phase 4 Constraints

- **Alpaca keys are paper trading only** — `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- **Telegram bot token** — `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (single admin chat, no multi-user auth needed)
- **All 97 existing tests must keep passing** throughout
- **No live API calls in tests** — all Alpaca and Telegram SDK calls must be mocked
- **Confirmation window** = 5 minutes; timeout → cancel with notification
- **Startup sync** — on FastAPI startup, pull open positions from Alpaca to overwrite local state
- **Daily loss reset** — `09:30 ET` daily (use a simple check-on-call approach: read today's date from SQLite, reset if stale)

---

## File Structure

```
db/
  schema.py               ← MODIFY: add positions + daily_loss + pending_confirmations tables

api/
  services/
    trade_service.py      ← CREATE: Alpaca wrapper + order lifecycle
  routes/
    trade.py              ← CREATE: POST /trade endpoint
  main.py                 ← MODIFY: register trade router + startup sync

telegram/
  __init__.py             ← CREATE: empty
  bot.py                  ← CREATE: long-polling bot runner
  handlers.py             ← CREATE: YES/NO confirmation handlers

tests/
  test_trade_service.py   ← CREATE
  test_trade_route.py     ← CREATE
  test_telegram_handlers.py ← CREATE

.env.example              ← MODIFY: add Alpaca + Telegram vars
requirements.txt          ← MODIFY: add alpaca-py, python-telegram-bot
```

---

## Task 1: DB Schema — positions + daily_loss + pending_confirmations

**Files:**
- Modify: `db/schema.py`
- Test: `tests/test_db_schema_v3.py` (new)

### Background

Three new tables:

- `positions` — local mirror of open positions (`symbol`, `qty`, `avg_entry_price`, `side`)
- `daily_loss` — persisted loss tracker so restart doesn't reset the guard (`trade_date TEXT PK`, `loss_usd REAL`)
- `pending_confirmations` — Telegram confirmation state (`order_id TEXT PK`, `symbol`, `action`, `qty`, `created_at TEXT`, `status TEXT DEFAULT 'pending'`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db_schema_v3.py`:

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_db_schema_v3.py -v
```

Expected: FAILED (tables don't exist yet)

- [ ] **Step 3: Add the three tables to `db/schema.py`**

Add inside `init_db`, after the existing `api_usage` table creation (before `conn.commit()`):

```python
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                symbol          TEXT NOT NULL,
                qty             REAL NOT NULL,
                avg_entry_price REAL NOT NULL,
                side            TEXT NOT NULL,
                PRIMARY KEY (symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_loss (
                trade_date  TEXT NOT NULL,
                loss_usd    REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (trade_date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_confirmations (
                order_id    TEXT NOT NULL,
                symbol      TEXT NOT NULL,
                action      TEXT NOT NULL,
                qty         REAL NOT NULL,
                created_at  TEXT NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY (order_id)
            )
        """)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_db_schema_v3.py -v
```

Expected: 4 PASSED

- [ ] **Step 5: Full suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

Expected: 101 passed

- [ ] **Step 6: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add db/schema.py tests/test_db_schema_v3.py
git commit -m "feat: add positions, daily_loss, pending_confirmations tables (Phase 4 DB)"
```

---

## Task 2: TradeService — Alpaca wrapper + order lifecycle

**Files:**
- Create: `api/services/trade_service.py`
- Test: `tests/test_trade_service.py`

### Background

`TradeService` wraps `alpaca.trading.TradingClient` and handles:

1. `sync_positions()` — fetch open positions from Alpaca, write to `positions` table
2. `submit_order(symbol, action, qty)` → returns `order_id` string
3. `cancel_order(order_id)` — cancel a pending order
4. `get_daily_loss(date_str)` → float (reads `daily_loss` table; 0.0 if no row)
5. `record_loss(date_str, loss_usd)` — upsert into `daily_loss`
6. `get_position_count()` → int (count of rows in `positions` table)

`TradingClient` is initialised lazily from env vars: `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL` (defaults to `https://paper-api.alpaca.markets`).

The class takes `db_path` in `__init__` for testability (same pattern as other services).

- [ ] **Step 1: Add `alpaca-py` and `python-telegram-bot` to requirements.txt**

Edit `requirements.txt` to add:
```
alpaca-py==0.32.0
python-telegram-bot==21.3
```

Install:
```bash
cd /Users/zakj/Documents/my/stock && pip install alpaca-py==0.32.0 python-telegram-bot==21.3
```

- [ ] **Step 2: Update `.env.example`**

Append to `.env.example`:
```
# Alpaca Paper Trading
ALPACA_API_KEY=your_alpaca_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_trade_service.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from db.schema import init_db
from api.services.trade_service import TradeService


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    return path


@pytest.fixture
def svc(db):
    return TradeService(db_path=db)


def test_get_daily_loss_returns_zero_when_no_record(svc):
    result = svc.get_daily_loss("2026-01-01")
    assert result == 0.0


def test_record_loss_and_retrieve(svc):
    svc.record_loss("2026-01-01", 15.50)
    assert svc.get_daily_loss("2026-01-01") == 15.50


def test_record_loss_upserts(svc):
    svc.record_loss("2026-01-01", 10.0)
    svc.record_loss("2026-01-01", 20.0)
    assert svc.get_daily_loss("2026-01-01") == 20.0


def test_get_position_count_zero_initially(svc):
    assert svc.get_position_count() == 0


def test_sync_positions_writes_to_db(svc):
    mock_position = MagicMock()
    mock_position.symbol = "AAPL"
    mock_position.qty = "10"
    mock_position.avg_entry_price = "185.50"
    mock_position.side = "long"

    with patch.object(svc, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = [mock_position]
        mock_get_client.return_value = mock_client
        svc.sync_positions()

    assert svc.get_position_count() == 1


def test_submit_order_returns_order_id(svc):
    mock_order = MagicMock()
    mock_order.id = "test-order-123"

    with patch.object(svc, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.submit_order.return_value = mock_order
        mock_get_client.return_value = mock_client
        order_id = svc.submit_order("AAPL", "buy", 1.0)

    assert order_id == "test-order-123"


def test_cancel_order_calls_alpaca(svc):
    with patch.object(svc, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        svc.cancel_order("test-order-456")

    mock_client.cancel_order_by_id.assert_called_once_with("test-order-456")
```

- [ ] **Step 4: Run to confirm failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_trade_service.py -v
```

Expected: ERROR (ImportError — TradeService not found)

- [ ] **Step 5: Create `api/services/trade_service.py`**

```python
import os
from db.schema import DEFAULT_DB_PATH, get_connection, init_db

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce


def _side(action: str) -> OrderSide:
    return OrderSide.BUY if action.lower() == "buy" else OrderSide.SELL


class TradeService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        init_db(db_path)
        self._client: TradingClient | None = None

    def _get_client(self) -> TradingClient:
        if self._client is None:
            self._client = TradingClient(
                api_key=os.environ["ALPACA_API_KEY"],
                secret_key=os.environ["ALPACA_SECRET_KEY"],
                paper=True,
            )
        return self._client

    # --- Positions ---

    def sync_positions(self) -> None:
        """Fetch open positions from Alpaca; overwrite local positions table."""
        client = self._get_client()
        positions = client.get_all_positions()
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM positions")
            conn.executemany(
                "INSERT INTO positions (symbol, qty, avg_entry_price, side) VALUES (?,?,?,?)",
                [
                    (p.symbol, float(p.qty), float(p.avg_entry_price), p.side)
                    for p in positions
                ],
            )
            conn.commit()
        finally:
            conn.close()

    def get_position_count(self) -> int:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute("SELECT COUNT(*) FROM positions").fetchone()
            return row[0]
        finally:
            conn.close()

    # --- Orders ---

    def submit_order(self, symbol: str, action: str, qty: float) -> str:
        """Submit a market order; return the Alpaca order_id string."""
        client = self._get_client()
        req = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=_side(action),
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(req)
        return str(order.id)

    def cancel_order(self, order_id: str) -> None:
        client = self._get_client()
        client.cancel_order_by_id(order_id)

    # --- Daily loss ---

    def get_daily_loss(self, date_str: str) -> float:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT loss_usd FROM daily_loss WHERE trade_date = ?", (date_str,)
            ).fetchone()
            return float(row["loss_usd"]) if row else 0.0
        finally:
            conn.close()

    def record_loss(self, date_str: str, loss_usd: float) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO daily_loss (trade_date, loss_usd) VALUES (?, ?)",
                (date_str, loss_usd),
            )
            conn.commit()
        finally:
            conn.close()
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_trade_service.py -v
```

Expected: 7 PASSED

- [ ] **Step 7: Full suite**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

Expected: 108 passed

- [ ] **Step 8: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/services/trade_service.py tests/test_trade_service.py requirements.txt .env.example
git commit -m "feat: TradeService — Alpaca paper trading wrapper with daily loss tracking"
```

---

## Task 3: Telegram Bot — confirmation flow

**Files:**
- Create: `telegram/__init__.py`
- Create: `telegram/bot.py`
- Create: `telegram/handlers.py`
- Test: `tests/test_telegram_handlers.py`

### Background

The Telegram bot serves one purpose: send a confirmation message for each pending trade, wait for `YES` or `NO` (or timeout), then update the `pending_confirmations` table so the `/trade` endpoint can poll it.

**Flow:**
1. `/trade` route inserts a row into `pending_confirmations` with `status='pending'` and sends a Telegram message via `send_confirmation()`
2. User replies `YES` or `NO` within 5 minutes
3. `handlers.py` handles the reply: updates `status` to `'confirmed'` or `'cancelled'`
4. `/trade` polls `pending_confirmations` every 2 seconds for up to 5 minutes; on `'confirmed'` → submits order; on `'cancelled'` or timeout → cancel with notification

**Key design:** The bot does NOT submit orders. It only updates the DB. The `/trade` route owns order submission. This keeps the bot stateless and testable.

`telegram/__init__.py` — empty (marks package)

`telegram/handlers.py` — pure functions that update the DB and optionally send reply messages. Testable without running a bot.

`telegram/bot.py` — bot entry point (long-polling). Called as `python -m telegram.bot` or as a background thread. Not tested directly (integration concern); the handlers it calls are tested.

**Sending messages:** `send_confirmation(order_id, symbol, action, qty, price_estimate)` — uses `python-telegram-bot`'s sync `Bot` to send a message to `TELEGRAM_CHAT_ID`. This is called from the `/trade` route before polling begins.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_telegram_handlers.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from db.schema import init_db, get_connection


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    # Seed a pending confirmation
    conn = get_connection(path)
    conn.execute(
        "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at) "
        "VALUES ('ord-1', 'AAPL', 'buy', 1.0, '2026-01-01T09:00:00')"
    )
    conn.commit()
    conn.close()
    return path


def test_handle_yes_sets_confirmed(db):
    from telegram.handlers import handle_confirmation
    handle_confirmation("ord-1", "YES", db_path=db)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'ord-1'"
        ).fetchone()
        assert row["status"] == "confirmed"
    finally:
        conn.close()


def test_handle_no_sets_cancelled(db):
    from telegram.handlers import handle_confirmation
    handle_confirmation("ord-1", "NO", db_path=db)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'ord-1'"
        ).fetchone()
        assert row["status"] == "cancelled"
    finally:
        conn.close()


def test_handle_invalid_reply_ignored(db):
    from telegram.handlers import handle_confirmation
    handle_confirmation("ord-1", "MAYBE", db_path=db)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'ord-1'"
        ).fetchone()
        assert row["status"] == "pending"
    finally:
        conn.close()


def test_get_pending_status(db):
    from telegram.handlers import get_confirmation_status
    status = get_confirmation_status("ord-1", db_path=db)
    assert status == "pending"


def test_get_missing_order_returns_none(db):
    from telegram.handlers import get_confirmation_status
    status = get_confirmation_status("nonexistent", db_path=db)
    assert status is None


def test_send_confirmation_calls_telegram(db):
    """send_confirmation() calls Bot.send_message with expected content."""
    from telegram.handlers import send_confirmation
    with patch("telegram.handlers.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot
        send_confirmation(
            order_id="ord-1",
            symbol="AAPL",
            action="buy",
            qty=1.0,
            price_estimate=185.0,
            db_path=db,
        )
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    text = call_kwargs[1].get("text") or call_kwargs[0][1]
    assert "AAPL" in text
    assert "buy" in text.lower()


def test_send_cancellation_notice_calls_telegram(db):
    """send_cancellation_notice() sends a message containing the reason."""
    from telegram.handlers import send_cancellation_notice
    with patch("telegram.handlers.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot
        send_cancellation_notice(order_id="ord-1", symbol="AAPL", reason="timeout", db_path=db)
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    text = call_kwargs[1].get("text") or call_kwargs[0][1]
    assert "AAPL" in text
    assert "timeout" in text.lower()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_telegram_handlers.py -v
```

Expected: ERROR (ImportError — telegram.handlers not found)

- [ ] **Step 3: Create `telegram/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `telegram/handlers.py`**

```python
import os
from typing import Optional
from db.schema import DEFAULT_DB_PATH, get_connection


def handle_confirmation(order_id: str, reply: str, *, db_path: str = DEFAULT_DB_PATH) -> None:
    """Update confirmation status based on user reply. Ignores unrecognised replies."""
    reply_upper = reply.strip().upper()
    if reply_upper not in ("YES", "NO"):
        return
    status = "confirmed" if reply_upper == "YES" else "cancelled"
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE pending_confirmations SET status = ? WHERE order_id = ?",
            (status, order_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_confirmation_status(order_id: str, *, db_path: str = DEFAULT_DB_PATH) -> Optional[str]:
    """Return the current status of a pending confirmation, or None if not found."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = ?", (order_id,)
        ).fetchone()
        return row["status"] if row else None
    finally:
        conn.close()


def send_confirmation(
    order_id: str,
    symbol: str,
    action: str,
    qty: float,
    price_estimate: float,
    *,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Send a trade confirmation request via Telegram. Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars."""
    from telegram import Bot  # python-telegram-bot

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = (
        f"Trade confirmation required\n"
        f"Order: {order_id}\n"
        f"Symbol: {symbol} | Action: {action.upper()} | Qty: {qty}\n"
        f"Est. price: ${price_estimate:.2f}\n"
        f"Reply YES to confirm or NO to cancel (5 min timeout)"
    )
    bot = Bot(token=token)
    bot.send_message(chat_id=chat_id, text=text)


def send_cancellation_notice(
    order_id: str,
    symbol: str,
    reason: str,
    *,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Send an order-cancelled notification via Telegram."""
    from telegram import Bot  # python-telegram-bot

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = (
        f"Order cancelled\n"
        f"Order: {order_id} | Symbol: {symbol}\n"
        f"Reason: {reason}"
    )
    bot = Bot(token=token)
    bot.send_message(chat_id=chat_id, text=text)
```

- [ ] **Step 5: Create `telegram/bot.py`**

**Note:** `vectorbt==0.26.2` is incompatible with `python-telegram-bot>=13`. The project uses `python-telegram-bot==12.8`, which uses `Updater`/`Dispatcher` (not `ApplicationBuilder`).

```python
"""
Telegram bot runner. Start with: python -m telegram.bot

The bot listens for messages in TELEGRAM_CHAT_ID.
User replies YES or NO to confirm or cancel the last pending trade order.

Uses python-telegram-bot v12 API (Updater + Dispatcher).
"""
import os
import logging
from telegram.ext import Updater, MessageHandler, Filters
from telegram import Update
from telegram.handlers import handle_confirmation
from db.schema import DEFAULT_DB_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory store of the last pending order_id sent to this chat
_pending_order_id: str | None = None


def set_pending_order(order_id: str) -> None:
    global _pending_order_id
    _pending_order_id = order_id


def message_handler(update: Update, context) -> None:
    global _pending_order_id
    if update.message is None or _pending_order_id is None:
        return
    text = (update.message.text or "").strip().upper()
    if text in ("YES", "NO"):
        handle_confirmation(_pending_order_id, text)
        _pending_order_id = None
        update.message.reply_text(f"Received: {text}")


def run_bot() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    logger.info("Telegram bot started, polling...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
```

- [ ] **Step 6: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_telegram_handlers.py -v
```

Expected: 7 PASSED

- [ ] **Step 7: Full suite**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

Expected: 115 passed

- [ ] **Step 8: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add telegram/__init__.py telegram/handlers.py telegram/bot.py tests/test_telegram_handlers.py
git commit -m "feat: Telegram bot — confirmation flow with SQLite state"
```

---

## Task 4: POST /trade — full order lifecycle

**Files:**
- Create: `api/routes/trade.py`
- Modify: `api/main.py` (register router + startup sync)
- Test: `tests/test_trade_route.py`

### Background

`POST /trade` receives `symbol`, `action` (`buy`|`sell`), `size` (fraction 0–1), `capital` and orchestrates the complete order lifecycle:

1. Compute `qty = floor(size * capital / price)` — use the last close price from `DataService`
2. Compute `proposed_trade_value = qty * price`
3. Run `RiskGate.check()` with current portfolio state from `TradeService`
4. If blocked → return `{"status": "blocked", "reason": "..."}` immediately (HTTP 200)
5. Insert row into `pending_confirmations` with `status='pending'`
6. Call `send_confirmation()` (Telegram message)
7. Poll `pending_confirmations` every 2 seconds for up to 300 seconds
8. If `'confirmed'` → `TradeService.submit_order()` → return `{"status": "submitted", "order_id": "..."}`
9. If `'cancelled'` or timeout → `{"status": "cancelled", "reason": "user_rejected"|"timeout"}`

Request body (JSON):
```json
{"symbol": "AAPL", "action": "buy", "size": 0.05, "capital": 10000.0, "start": "2024-01-01", "end": "2024-12-31"}
```

`start`/`end` are used to fetch the price series (to get last close price).

Response codes: always 200 (business outcomes, not errors); 422 on bad input.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_trade_route.py`:

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from api.main import app

client = TestClient(app)

TRADE_BODY = {
    "symbol": "AAPL",
    "action": "buy",
    "size": 0.05,
    "capital": 10000.0,
    "start": "2024-01-01",
    "end": "2024-12-31",
}

MOCK_PRICES = [
    {"date": "2024-12-30", "open": 252.0, "high": 255.0,
     "low": 250.0, "close": 253.0, "volume": 45000000},
]


def _make_risk_allowed():
    r = MagicMock()
    r.allowed = True
    r.reason = None
    return r


def _make_risk_blocked(reason="Daily loss limit"):
    r = MagicMock()
    r.allowed = False
    r.reason = reason
    return r


def test_trade_returns_200():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.submit_order.return_value = "ord-abc"
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code == 200


def test_trade_risk_blocked_returns_blocked_status():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade:
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_blocked("Capital too low")
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code == 200
    assert resp.json()["status"] == "blocked"
    assert "Capital too low" in resp.json()["reason"]


def test_trade_no_price_data_returns_422_or_error():
    with patch("api.routes.trade.DataService") as MockData:
        MockData.return_value.fetch.return_value = []
        resp = client.post("/trade", json=TRADE_BODY)
    assert resp.status_code in (200, 404, 422)
    if resp.status_code == 200:
        assert resp.json()["status"] in ("error", "blocked")


def test_trade_confirmed_returns_submitted():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="confirmed"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.submit_order.return_value = "ord-xyz"
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "submitted"
    assert body["order_id"] == "ord-xyz"


def test_trade_timeout_returns_cancelled():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="timeout"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["reason"] == "timeout"


def test_trade_user_rejected_returns_cancelled():
    with patch("api.routes.trade.DataService") as MockData, \
         patch("api.routes.trade.RiskGate") as MockGate, \
         patch("api.routes.trade.TradeService") as MockTrade, \
         patch("api.routes.trade.send_confirmation"), \
         patch("api.routes.trade._poll_confirmation", return_value="cancelled"), \
         patch("api.routes.trade._insert_pending"):
        MockData.return_value.fetch.return_value = MOCK_PRICES
        MockGate.return_value.check.return_value = _make_risk_allowed()
        MockTrade.return_value.get_daily_loss.return_value = 0.0
        MockTrade.return_value.get_position_count.return_value = 0
        resp = client.post("/trade", json=TRADE_BODY)
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["reason"] == "user_rejected"


def test_trade_missing_fields_returns_422():
    resp = client.post("/trade", json={"symbol": "AAPL"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_trade_route.py -v
```

Expected: FAILED (ImportError — trade route not registered)

- [ ] **Step 3: Create `api/routes/trade.py`**

```python
import math
import time
import uuid
from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.services.data_service import DataService
from api.services.risk_service import RiskGate
from api.services.trade_service import TradeService
from db.schema import DEFAULT_DB_PATH, get_connection, init_db
from telegram.handlers import get_confirmation_status, send_confirmation, send_cancellation_notice

router = APIRouter()

CONFIRMATION_TIMEOUT_SECS = 300  # 5 minutes
POLL_INTERVAL_SECS = 2


class TradeRequest(BaseModel):
    symbol: str
    action: str          # "buy" | "sell"
    size: float          # fraction of capital, e.g. 0.05
    capital: float       # total portfolio capital in $
    start: str           # YYYY-MM-DD for price fetch
    end: str             # YYYY-MM-DD for price fetch


def _insert_pending(order_id: str, symbol: str, action: str, qty: float, db_path: str = DEFAULT_DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        from datetime import datetime
        conn.execute(
            "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, symbol, action, qty, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _poll_confirmation(order_id: str, db_path: str = DEFAULT_DB_PATH) -> str:
    """Poll until status is 'confirmed' or 'cancelled', or timeout. Returns final status string."""
    deadline = time.time() + CONFIRMATION_TIMEOUT_SECS
    while time.time() < deadline:
        status = get_confirmation_status(order_id, db_path=db_path)
        if status in ("confirmed", "cancelled"):
            return status
        time.sleep(POLL_INTERVAL_SECS)
    return "timeout"


@router.post("/trade")
def post_trade(req: TradeRequest):
    today = date.today().isoformat()
    trade_svc = TradeService()
    data_svc = DataService()
    risk_gate = RiskGate()

    prices = data_svc.fetch(req.symbol.upper(), req.start, req.end)
    if not prices:
        return {"status": "error", "reason": f"No price data for {req.symbol}"}

    last_price = prices[-1]["close"]
    qty = max(1, math.floor(req.size * req.capital / last_price))
    proposed_value = qty * last_price

    daily_loss = trade_svc.get_daily_loss(today)
    position_count = trade_svc.get_position_count()

    risk_result = risk_gate.check(
        capital=req.capital,
        daily_loss=daily_loss,
        current_positions=position_count,
        proposed_trade_value=proposed_value,
    )
    if not risk_result.allowed:
        return {"status": "blocked", "reason": risk_result.reason}

    order_id = str(uuid.uuid4())
    _insert_pending(order_id, req.symbol.upper(), req.action, qty)
    send_confirmation(
        order_id=order_id,
        symbol=req.symbol.upper(),
        action=req.action,
        qty=qty,
        price_estimate=last_price,
    )

    outcome = _poll_confirmation(order_id)

    if outcome == "confirmed":
        alpaca_order_id = trade_svc.submit_order(req.symbol.upper(), req.action, qty)
        return {"status": "submitted", "order_id": alpaca_order_id, "qty": qty, "price_estimate": last_price}

    reason = "user_rejected" if outcome == "cancelled" else "timeout"
    send_cancellation_notice(order_id=order_id, symbol=req.symbol.upper(), reason=reason)
    return {"status": "cancelled", "reason": reason}
```

- [ ] **Step 4: Register router in `api/main.py` + add startup sync**

Replace `api/main.py` with:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes.data import router as data_router
from api.routes.backtest import router as backtest_router
from api.routes.sentiment import router as sentiment_router
from api.routes.signal import router as signal_router
from api.routes.trade import router as trade_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: sync positions from Alpaca (no-op if creds not set)
    try:
        from api.services.trade_service import TradeService
        TradeService().sync_positions()
    except Exception:
        pass  # Alpaca creds not configured — skip sync
    yield


app = FastAPI(title="AI Quant System", version="0.1.0", lifespan=lifespan)

app.include_router(data_router)
app.include_router(backtest_router)
app.include_router(sentiment_router)
app.include_router(signal_router)
app.include_router(trade_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run route tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_trade_route.py -v
```

Expected: 7 PASSED

- [ ] **Step 6: Full suite**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

Expected: 122 passed

- [ ] **Step 7: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/routes/trade.py api/main.py tests/test_trade_route.py
git commit -m "feat: POST /trade with Telegram confirmation + Alpaca order lifecycle (Phase 4 complete)"
```

---

## Phase 4 Completion Criteria

- [ ] `pytest tests/ -q` → 122 passed (97 existing + 4 schema + 7 trade service + 7 telegram + 7 route)
- [ ] `POST /trade {"symbol":"AAPL","action":"buy","size":0.05,"capital":10000,"start":"2024-01-01","end":"2024-12-31"}` → `{"status":"blocked"}` (no Alpaca creds) or `{"status":"submitted"}` with real creds
- [ ] With capital=150 (below min $200) → `{"status":"blocked","reason":"Capital $150.00 below minimum..."}`
- [ ] `telegram/bot.py` runnable standalone: `python -m telegram.bot` (with real bot token)
- [ ] FastAPI startup sync does not crash when `ALPACA_API_KEY` is not set

---

## 下一步

Phase 4 完成后继续 Phase 5：OpenClaw Skills 封装 + 实盘准备（`docs/superpowers/plans/2026-03-20-phase5-openclaw-live.md`）
