
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, LOG_LEVEL

from database import init_db, close_db

from admin import router as admin_router
from bot_commands import router as bot_commands_router
from channels import router as channels_router
from private_channels import router as private_channels_router
from panels import router as panels_router
from services import router as services_router
from reports import router as reports_router
from order_commands import router as order_commands_router
from system_commands import router as system_commands_router
from order_engine import router as order_engine_router

from scheduler import start_scheduler, stop_scheduler


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


# ==========================================
# MAIN FUNCTION
# ==========================================

async def main():

    bot = None
    database_initialized = False

    try:
        logger.info("Starting Telegram SMM Bot...")

        # Create Telegram bot
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML
            )
        )

        # Create dispatcher
        dp = Dispatcher(
            storage=MemoryStorage()
        )

        # ==================================
        # REGISTER ROUTERS
        # ==================================

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

        logger.info("All routers registered.")

        # ==================================
        # DATABASE INITIALIZATION
        # ==================================

        logger.info("Initializing PostgreSQL database...")

        await init_db()
        database_initialized = True

        logger.info("Database initialized successfully.")

        # ==================================
        # TELEGRAM CONNECTION
        # ==================================

        bot_info = await bot.get_me()

        logger.info(
            "Bot connected successfully: @%s | ID: %s",
            bot_info.username,
            bot_info.id
        )

        # ==================================
        # START ORDER STATUS SCHEDULER
        # ==================================

        start_scheduler()

        # ==================================
        # REMOVE WEBHOOK
        # ==================================

        await bot.delete_webhook(
            drop_pending_updates=False
        )

        # ==================================
        # START POLLING
        # ==================================

        logger.info("Telegram polling started.")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    except asyncio.CancelledError:
        logger.warning("Bot polling cancelled.")
        raise

    except Exception:
        logger.exception("Bot startup/runtime error.")
        raise

    finally:

        logger.info("Shutting down bot...")

        # Stop scheduler
        try:
            stop_scheduler()
        except Exception:
            logger.exception("Scheduler shutdown failed.")

        # Close database
        if database_initialized:
            try:
                await close_db()
                logger.info("Database connection closed.")
            except Exception:
                logger.exception("Database shutdown failed.")

        # Close Telegram session
        if bot is not None:
            try:
                await bot.session.close()
                logger.info("Telegram session closed.")
            except Exception:
                logger.exception("Telegram session shutdown failed.")

        logger.info("Bot shutdown completed.")


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")

    except Exception:
        logging.getLogger(__name__).exception(
            "Application exited with an error."
        )
