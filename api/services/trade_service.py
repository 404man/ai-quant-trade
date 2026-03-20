import os
from typing import Optional
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
        self._client: Optional[TradingClient] = None

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
