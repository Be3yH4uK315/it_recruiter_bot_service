import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from aiogram import Bot, Dispatcher
from app.core.config import BOT_TOKEN
from app.handlers import common, candidate_registration, employer_search, candidate_profile
from app.middlewares.logging import LoggingMiddleware, CustomFormatter

def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_file = os.getenv('LOG_FILE', 'bot.log')
    
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    file_handler.setLevel(log_level)
    file_handler.setFormatter(CustomFormatter('%(asctime)s - %(name)s - %(levelname)s - %(user_id)s - %(message)s'))  # Используем custom formatter
    
    logging.getLogger().addHandler(file_handler)

async def main():
    setup_logging()
    
    bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
    
    dp = Dispatcher()
    
    dp.message.outer_middleware(LoggingMiddleware())
    dp.callback_query.outer_middleware(LoggingMiddleware())
    
    dp.include_router(common.router)
    dp.include_router(candidate_registration.router)
    dp.include_router(employer_search.router)
    dp.include_router(candidate_profile.router)
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"Critical error starting bot: {e}", exc_info=True)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped gracefully")
    except Exception as e:
        logging.critical(f"Unexpected error in main: {e}", exc_info=True)