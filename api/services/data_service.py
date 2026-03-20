import yfinance as yf
import pandas as pd
from datetime import date as _date
from db.schema import get_connection, init_db, DEFAULT_DB_PATH


class DataService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        init_db(db_path)

    def fetch(self, symbol: str, start: str, end: str) -> list[dict]:
        """
        Returns day-bar data for symbol in [start, end] date range.
        Reads from SQLite cache first; fetches from yfinance on cache miss.
        """
        symbol = symbol.upper()

        try:
            _date.fromisoformat(start)
            _date.fromisoformat(end)
        except ValueError as e:
            raise ValueError(f"Invalid date format (expected YYYY-MM-DD): {e}") from e

        if self._is_range_cached(symbol, start, end):
            return self._read_cache(symbol, start, end)

        raw = self._fetch_yfinance(symbol, start, end)
        if raw:
            self._write_cache(symbol, raw)
            self._record_cache_range(symbol, start, end)
        return raw

    def _is_range_cached(self, symbol: str, start: str, end: str) -> bool:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT 1 FROM cache_ranges WHERE symbol = ? AND start = ? AND end = ?",
                (symbol, start, end),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def _record_cache_range(self, symbol: str, start: str, end: str) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO cache_ranges (symbol, start, end) VALUES (?, ?, ?)",
                (symbol, start, end),
            )
            conn.commit()
        finally:
            conn.close()

    def _read_cache(self, symbol: str, start: str, end: str) -> list[dict]:
        conn = get_connection(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT date, open, high, low, close, volume FROM price_cache "
                "WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date",
                (symbol, start, end),
            )
            rows = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
        return rows

    def _fetch_yfinance(self, symbol: str, start: str, end: str) -> list[dict]:
        df = yf.download(symbol, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return []
        # yfinance >= 0.2.18 returns MultiIndex columns for single ticker downloads
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df["Date"] = df["Date"].astype(str).str[:10]
        records = [
            {
                "date": str(row["Date"])[:10],
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            }
            for row in df.to_dict("records")
        ]
        return records

    def _write_cache(self, symbol: str, records: list[dict]) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO price_cache "
                "(symbol, date, open, high, low, close, volume) VALUES (?,?,?,?,?,?,?)",
                [
                    (symbol, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"])
                    for r in records
                ],
            )
            conn.commit()
        finally:
            conn.close()
