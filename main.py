
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN
from database import init_db, close_db
from channels import router as channels_router
from reports import router as reports_router
from admin import router as admin_router
from scheduler import start_scheduler, stop_scheduler


async def main():

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        )
    )

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Register command routers
    dp.include_router(admin_router)
    dp.include_router(channels_router)
    dp.include_router(reports_router)

    # Start command handler
    @dp.message(CommandStart())
    async def start_command(message: Message):
        await message.answer(
            "👋 Welcome!\n\n"
            "Your Telegram Bot is running successfully.\n\n"
            "Use the available admin commands to manage your channels."
        )

    # Unknown message handler
    @dp.message()
    async def unknown_message(message: Message):
        await message.answer(
            "❓ Sorry, I don't understand this command.\n\n"
            "Please send /start or use a valid bot command."
        )

    database_initialized = False

    try:
        # Initialize PostgreSQL
        await init_db()
        database_initialized = True

        # Start scheduler
        start_scheduler()

        logging.info("Telegram bot is starting...")

        # Start polling
        await dp.start_polling(bot)

    except Exception:
        logging.exception("Bot stopped because of an error")
        raise

    finally:
        stop_scheduler()

        if database_initialized:
            await close_db()

        await bot.session.close()

        logging.info("Telegram bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
