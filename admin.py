
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID

logger = logging.getLogger(__name__)

router = Router()


def is_owner(user_id: int) -> bool:
    """Check whether the Telegram user is the bot owner."""
    return user_id == OWNER_ID


async def owner_only(message: Message) -> bool:
    """Allow commands only for the configured owner."""

    if not message.from_user:
        return False

    if is_owner(message.from_user.id):
        return True

    await message.answer(
        "❌ You are not authorized to use this command."
    )

    logger.warning(
        "Unauthorized command attempt by user ID: %s",
        message.from_user.id
    )

    return False


@router.message(Command("admin"))
async def admin_command(message: Message):
    if not await owner_only(message):
        return

    await message.answer(
        "👑 <b>Admin Panel</b>\n\n"
        "Welcome, Owner!\n\n"
        "Available commands:\n"
        "/addchannel\n"
        "/removechannel\n"
        "/channels\n"
        "/setqty\n"
        "/getqty\n"
        "/startqty\n"
        "/stopqty\n"
        "/report24\n"
        "/report72\n"
        "/reportday\n"
        "/reportweek\n"
        "/reportmonth",
        parse_mode="HTML"
    )
