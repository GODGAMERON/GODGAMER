
import asyncio
import logging

from aiogram import Bot, Dispatcher

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

    database_initialized = False

    try:
        # Initialize PostgreSQL
        await init_db()
        database_initialized = True

        # Start background scheduler
        start_scheduler()

        logging.info("Telegram bot is starting...")

        # Start polling
        await dp.start_polling(bot)

    except Exception:
        logging.exception("Bot stopped because of an error")
        raise

    finally:
        # Stop scheduler
        stop_scheduler()

        # Close database
        if database_initialized:
            await close_db()

        # Close Telegram session
        await bot.session.close()

        logging.info("Telegram bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
