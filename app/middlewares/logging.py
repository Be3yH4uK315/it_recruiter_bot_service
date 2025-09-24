import logging
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

logger = logging.getLogger(__name__)

class CustomFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, 'user_id'):
            record.user_id = 'system'
        return super().format(record)

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any]
    ) -> Any:
        user = event.from_user if hasattr(event, 'from_user') else None
        user_id = user.id if user else 'unknown'
        data['user_id'] = user_id
        
        try:
            if isinstance(event, Message):
                text = event.text or event.caption or "Non-text message"
                logger.info(f"Message from user {user_id}: {text}", extra={'user_id': user_id})
            elif isinstance(event, CallbackQuery):
                callback_data = event.data
                logger.info(f"Callback from user {user_id}: {callback_data}", extra={'user_id': user_id})
            
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error handling event for user {user_id}: {e}", exc_info=True, extra={'user_id': user_id})
            if isinstance(event, (Message, CallbackQuery)):
                target = event.message if isinstance(event, CallbackQuery) else event
                await target.answer("❌ Внутренняя ошибка. Попробуйте позже или обратитесь в поддержку.")
            raise