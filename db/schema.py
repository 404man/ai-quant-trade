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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol    TEXT PRIMARY KEY,
                notes     TEXT NOT NULL DEFAULT '',
                added_at  TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()
