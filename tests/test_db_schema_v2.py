import sqlite3
import tempfile
import os
from db.schema import init_db


def test_init_db_creates_sentiment_cache_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sentiment_cache'"
        )
        assert cursor.fetchone() is not None
        conn.close()
    finally:
        os.unlink(db_path)


def test_sentiment_cache_has_required_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(sentiment_cache)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"symbol", "cached_at", "sentiment", "confidence"}.issubset(columns)
        conn.close()
    finally:
        os.unlink(db_path)


def test_init_db_creates_api_usage_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_usage'"
        )
        assert cursor.fetchone() is not None
        conn.close()
    finally:
        os.unlink(db_path)


def test_api_usage_has_required_columns():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(api_usage)")
        columns = {row[1] for row in cursor.fetchall()}
        assert {"usage_date", "api_name", "call_count"}.issubset(columns)
        conn.close()
    finally:
        os.unlink(db_path)
