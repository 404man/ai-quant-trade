import os
from typing import Optional
from db.schema import DEFAULT_DB_PATH, get_connection
from telegram import Bot


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
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    text = (
        f"Order cancelled\n"
        f"Order: {order_id} | Symbol: {symbol}\n"
        f"Reason: {reason}"
    )
    bot = Bot(token=token)
    bot.send_message(chat_id=chat_id, text=text)
