import sqlite3
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "cache.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_cache (
                symbol  TEXT NOT NULL,
                date    TEXT NOT NULL,
                open    REAL NOT NULL,
                high    REAL NOT NULL,
                low     REAL NOT NULL,
                close   REAL NOT NULL,
                volume  INTEGER NOT NULL,
                PRIMARY KEY (symbol, date)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_ranges (
                symbol TEXT NOT NULL,
                start  TEXT NOT NULL,
                end    TEXT NOT NULL,
                PRIMARY KEY (symbol, start, end)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_cache (
                symbol      TEXT NOT NULL,
                cached_at   TEXT NOT NULL,
                sentiment   TEXT NOT NULL,
                confidence  REAL NOT NULL,
                PRIMARY KEY (symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                usage_date  TEXT NOT NULL,
                api_name    TEXT NOT NULL,
                call_count  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (usage_date, api_name)
            )
        """)
        conn.commit()
    finally:
        conn.close()
