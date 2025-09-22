import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            user_id = event.from_user.id
            text = event.text or event.caption or "Non-text message"
            logger.info(f"Message from user {user_id}: {text}")
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id
            callback_data = event.data
            logger.info(f"Callback from user {user_id}: {callback_data}")
        return await handler(event, data)