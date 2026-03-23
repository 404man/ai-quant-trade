# Console UI — Backend: GET /confirmations

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /confirmations` endpoint that returns the last 50 rows from `pending_confirmations` sorted by `created_at` DESC.

**Architecture:** One new route file following the exact same pattern as all existing routes (read-only, no service layer needed — direct DB read). Register in `api/main.py`.

**Tech Stack:** Python 3.11, FastAPI, SQLite (existing `db/schema.py` helpers), pytest

---

## File Structure

```
api/routes/confirmations.py    ← CREATE: GET /confirmations route
api/main.py                    ← MODIFY: register confirmations router
tests/test_confirmations_route.py  ← CREATE: 3 tests
```

---

## Task 1: GET /confirmations endpoint

**Files:**
- Create: `api/routes/confirmations.py`
- Modify: `api/main.py`
- Test: `tests/test_confirmations_route.py`

### Background

The `pending_confirmations` table (created in Phase 4) has columns:
`order_id TEXT PK, symbol TEXT, action TEXT, qty REAL, created_at TEXT, status TEXT DEFAULT 'pending'`

The endpoint reads it directly — no service abstraction needed, it's a single SELECT.

Response: JSON array, newest first, max 50 rows.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_confirmations_route.py`:

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_confirmations_route.py -v 2>&1 | head -20
```

Expected: ImportError or 404 for `/confirmations`

- [ ] **Step 3: Create `api/routes/confirmations.py`**

```python
from fastapi import APIRouter
from db.schema import DEFAULT_DB_PATH, get_connection

router = APIRouter()


@router.get("/confirmations")
def get_confirmations():
    conn = get_connection(DEFAULT_DB_PATH)
    try:
        rows = conn.execute(
            "SELECT order_id, symbol, action, qty, created_at, status "
            "FROM pending_confirmations "
            "ORDER BY created_at DESC "
            "LIMIT 50"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

- [ ] **Step 4: Register router in `api/main.py`**

Read `api/main.py` first, then add:
- Import: `from api.routes.confirmations import router as confirmations_router`
- Registration: `app.include_router(confirmations_router)`

- [ ] **Step 5: Run tests**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/test_confirmations_route.py -v
```

Expected: 5 PASSED

- [ ] **Step 6: Full suite — no regressions**

```bash
cd /Users/zakj/Documents/my/stock && python -m pytest tests/ -q
```

Expected: 127 passed (122 existing + 5 new)

- [ ] **Step 7: Commit**

```bash
cd /Users/zakj/Documents/my/stock && git add api/routes/confirmations.py api/main.py tests/test_confirmations_route.py
git commit -m "feat: GET /confirmations endpoint for console UI message center"
```

---

## Completion Criteria

- [ ] `pytest tests/ -q` → 127 passed
- [ ] `curl http://localhost:8000/confirmations` returns JSON array (start server first with `uvicorn api.main:app --reload`)
