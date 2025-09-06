import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.core.config import BOT_TOKEN
from app.handlers import common, candidate_registration, employer_search


logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher()

    dp.include_router(common.router)
    dp.include_router(candidate_registration.router)
    dp.include_router(employer_search.router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
