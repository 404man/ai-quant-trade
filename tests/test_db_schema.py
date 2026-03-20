import sqlite3
import tempfile
import os
import pytest
from db.schema import get_connection, init_db


def test_init_db_creates_price_cache_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='price_cache'"
        )
        assert cursor.fetchone() is not None
        conn.close()
    finally:
        os.unlink(db_path)


def test_price_cache_has_required_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(price_cache)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"symbol", "date", "open", "high", "low", "close", "volume"}.issubset(columns)
        conn.close()
    finally:
        os.unlink(db_path)


def test_get_connection_returns_connection():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = get_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()
    finally:
        os.unlink(db_path)
