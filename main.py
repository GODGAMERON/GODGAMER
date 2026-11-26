
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, LOG_LEVEL

from database import init_db, close_db

from admin import router as admin_router
from channels import router as channels_router
from private_channels import router as private_channels_router
from reports import router as reports_router
from panels import router as panels_router
from services import router as services_router
from order_engine import router as order_engine_router
from bot_commands import router as bot_commands_router
from order_commands import router as order_commands_router
from system_commands import router as system_commands_router

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

    dp = Dispatcher(storage=MemoryStorage())

    # Register all routers
    dp.include_router(admin_router)
    dp.include_router(bot_commands_router)
    dp.include_router(channels_router)
    dp.include_router(private_channels_router)
    dp.include_router(panels_router)
    dp.include_router(services_router)
    dp.include_router(reports_router)
    dp.include_router(order_commands_router)
    dp.include_router(system_commands_router)
    dp.include_router(order_engine_router)

    try:
        logger.info("Initializing database...")
        await init_db()

        bot_info = await bot.get_me()

        logger.info(
            "Connected to bot @%s | ID: %s",
            bot_info.username,
            bot_info.id
        )

        start_scheduler()

        await bot.delete_webhook(drop_pending_updates=False)

        logger.info("Starting Telegram polling...")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    except Exception:
        logger.exception("Bot startup/runtime error")
        raise

    finally:
        logger.info("Stopping bot...")

        stop_scheduler()
        await close_db()
        await bot.session.close()

        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
