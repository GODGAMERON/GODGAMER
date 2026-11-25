
import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db, close_db
from channels import router as channels_router
from reports import router as reports_router


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(channels_router)
    dp.include_router(reports_router)

    try:
        await init_db()
        logging.info("Bot is starting...")
        await dp.start_polling(bot)

    finally:
        await close_db()
        await bot.session.close()
        logging.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
