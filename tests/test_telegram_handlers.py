import pytest
from unittest.mock import patch, MagicMock
from db.schema import init_db, get_connection


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path)
    # Seed a pending confirmation
    conn = get_connection(path)
    conn.execute(
        "INSERT INTO pending_confirmations (order_id, symbol, action, qty, created_at) "
        "VALUES ('ord-1', 'AAPL', 'buy', 1.0, '2026-01-01T09:00:00')"
    )
    conn.commit()
    conn.close()
    return path


def test_handle_yes_sets_confirmed(db):
    from tg.handlers import handle_confirmation
    handle_confirmation("ord-1", "YES", db_path=db)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'ord-1'"
        ).fetchone()
        assert row["status"] == "confirmed"
    finally:
        conn.close()


def test_handle_no_sets_cancelled(db):
    from tg.handlers import handle_confirmation
    handle_confirmation("ord-1", "NO", db_path=db)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'ord-1'"
        ).fetchone()
        assert row["status"] == "cancelled"
    finally:
        conn.close()


def test_handle_invalid_reply_ignored(db):
    from tg.handlers import handle_confirmation
    handle_confirmation("ord-1", "MAYBE", db_path=db)
    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT status FROM pending_confirmations WHERE order_id = 'ord-1'"
        ).fetchone()
        assert row["status"] == "pending"
    finally:
        conn.close()


def test_get_pending_status(db):
    from tg.handlers import get_confirmation_status
    status = get_confirmation_status("ord-1", db_path=db)
    assert status == "pending"


def test_get_missing_order_returns_none(db):
    from tg.handlers import get_confirmation_status
    status = get_confirmation_status("nonexistent", db_path=db)
    assert status is None


def test_send_confirmation_calls_telegram(db):
    """send_confirmation() calls Bot.send_message with expected content."""
    from tg.handlers import send_confirmation
    env_vars = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "test-chat"}
    with patch.dict("os.environ", env_vars), patch("tg.handlers.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot
        send_confirmation(
            order_id="ord-1",
            symbol="AAPL",
            action="buy",
            qty=1.0,
            price_estimate=185.0,
            db_path=db,
        )
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    text = call_kwargs[1].get("text") or call_kwargs[0][1]
    assert "AAPL" in text
    assert "buy" in text.lower()


def test_send_cancellation_notice_calls_telegram(db):
    """send_cancellation_notice() sends a message containing the reason."""
    from tg.handlers import send_cancellation_notice
    env_vars = {"TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "test-chat"}
    with patch.dict("os.environ", env_vars), patch("tg.handlers.Bot") as MockBot:
        mock_bot = MagicMock()
        MockBot.return_value = mock_bot
        send_cancellation_notice(order_id="ord-1", symbol="AAPL", reason="timeout", db_path=db)
    mock_bot.send_message.assert_called_once()
    call_kwargs = mock_bot.send_message.call_args
    text = call_kwargs[1].get("text") or call_kwargs[0][1]
    assert "AAPL" in text
    assert "timeout" in text.lower()
