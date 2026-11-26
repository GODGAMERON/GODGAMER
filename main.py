
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, LOG_LEVEL

from database import init_db, close_db

from admin import router as admin_router
from channels import router as channels_router
from private_channels import router as private_channels_router
from reports import router as reports_router

from scheduler import start_scheduler, stop_scheduler


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    # Register routers
    dp.include_router(admin_router)
    dp.include_router(channels_router)
    dp.include_router(private_channels_router)
    dp.include_router(reports_router)

    try:
        logger.info("Initializing database...")
        await init_db()

        logger.info("Checking Telegram bot...")
        bot_info = await bot.get_me()

        logger.info(
            "Bot connected: @%s | ID: %s",
            bot_info.username,
            bot_info.id
        )

        # Start background scheduler
        start_scheduler()

        logger.info("Starting Telegram polling...")

        # Remove old webhook before polling
        await bot.delete_webhook(drop_pending_updates=False)

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    except Exception:
        logger.exception("Bot startup/runtime error")
        raise

    finally:
        logger.info("Stopping bot services...")

        stop_scheduler()

        await close_db()

        await bot.session.close()

        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
