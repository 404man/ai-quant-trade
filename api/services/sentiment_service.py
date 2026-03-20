import json
import re
import os
from datetime import datetime, timezone, timedelta

import anthropic

from db.schema import get_connection, init_db, DEFAULT_DB_PATH

SENTIMENT_CACHE_TTL_HOURS = 1
DAILY_CLAUDE_CALL_LIMIT = 50
FALLBACK_RESPONSE = {"sentiment": "neutral", "confidence": 0.5}

_VALID_SENTIMENTS = {"bullish", "bearish", "neutral"}


class SentimentService:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        init_db(db_path)
        self._client = None  # lazy-initialized on first real API call

    def get_sentiment(self, symbol: str) -> dict:
        symbol = symbol.upper()

        # 1. Return cached result if fresh
        cached = self._read_cache(symbol)
        if cached is not None:
            return cached

        # 2. Check daily call limit
        if not self._try_increment_usage():
            return FALLBACK_RESPONSE.copy()

        # 3. Call Claude API
        try:
            result = self._call_claude(symbol)
        except Exception:
            self._decrement_usage()  # roll back — don't penalize transient errors
            return FALLBACK_RESPONSE.copy()

        # 4. Cache and return
        self._write_cache(symbol, result)
        return result

    def _call_claude(self, symbol: str) -> dict:
        if self._client is None:
            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

        prompt = (
            f"You are a financial sentiment analyst. "
            f"Based on your knowledge of {symbol} stock, assess the overall "
            f"market sentiment. Consider: recent earnings trends, analyst consensus, "
            f"sector momentum, and known catalysts or risks.\n\n"
            f"Respond with ONLY a JSON object:\n"
            f'{{"sentiment": "<bullish|bearish|neutral>", "confidence": <0.0-1.0>}}\n\n'
            f"confidence: 0.5 = uncertain, 0.9 = very clear. No explanation."
        )

        message = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()

        # Strip markdown code fences if present
        match = re.search(r'\{[^}]+\}', text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in Claude response: {text!r}")
        parsed = json.loads(match.group())

        if parsed.get("sentiment") not in _VALID_SENTIMENTS:
            raise ValueError(f"Invalid sentiment value: {parsed.get('sentiment')!r}")
        confidence = float(parsed["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise ValueError(f"Confidence out of range: {confidence}")

        return {"sentiment": parsed["sentiment"], "confidence": round(confidence, 2)}

    def _read_cache(self, symbol: str) -> dict | None:
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT sentiment, confidence, cached_at FROM sentiment_cache WHERE symbol = ?",
                (symbol,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            return None

        cached_at = datetime.fromisoformat(row["cached_at"])
        if cached_at.tzinfo is None:
            cached_at = cached_at.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - cached_at
        if age > timedelta(hours=SENTIMENT_CACHE_TTL_HOURS):
            return None  # expired

        return {"sentiment": row["sentiment"], "confidence": float(row["confidence"])}

    def _write_cache(self, symbol: str, result: dict) -> None:
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO sentiment_cache "
                "(symbol, cached_at, sentiment, confidence) VALUES (?, ?, ?, ?)",
                (
                    symbol,
                    datetime.now(timezone.utc).isoformat(),
                    result["sentiment"],
                    float(result["confidence"]),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def _try_increment_usage(self) -> bool:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT call_count FROM api_usage WHERE usage_date = ? AND api_name = 'claude'",
                (today,),
            ).fetchone()
            current = row["call_count"] if row else 0
            if current >= DAILY_CLAUDE_CALL_LIMIT:
                return False
            conn.execute(
                "INSERT OR REPLACE INTO api_usage (usage_date, api_name, call_count) "
                "VALUES (?, 'claude', ?)",
                (today, current + 1),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def _decrement_usage(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = get_connection(self.db_path)
        try:
            row = conn.execute(
                "SELECT call_count FROM api_usage WHERE usage_date = ? AND api_name = 'claude'",
                (today,),
            ).fetchone()
            if row and row["call_count"] > 0:
                conn.execute(
                    "INSERT OR REPLACE INTO api_usage (usage_date, api_name, call_count) "
                    "VALUES (?, 'claude', ?)",
                    (today, row["call_count"] - 1),
                )
                conn.commit()
        finally:
            conn.close()
