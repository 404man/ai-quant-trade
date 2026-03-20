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
    conn.commit()
    conn.close()
