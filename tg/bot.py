"""
Telegram bot runner. Start with: python -m tg.bot

Uses python-telegram-bot v12 API (Updater + Dispatcher).
vectorbt==0.26.2 is incompatible with python-telegram-bot>=13.
"""
import os
import logging
from telegram.ext import Updater, MessageHandler, Filters
from tg.handlers import handle_confirmation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_pending_order_id = None


def set_pending_order(order_id: str) -> None:
    global _pending_order_id
    _pending_order_id = order_id


def message_handler(update, context) -> None:
    global _pending_order_id
    if update.message is None or _pending_order_id is None:
        return
    text = (update.message.text or "").strip().upper()
    if text in ("YES", "NO"):
        handle_confirmation(_pending_order_id, text)
        _pending_order_id = None
        update.message.reply_text(f"Received: {text}")


def run_bot() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    updater = Updater(token=token, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    logger.info("Telegram bot started, polling...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
