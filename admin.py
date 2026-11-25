import logging
from functools import wraps

from config import OWNER_ID

logger = logging.getLogger(name)


def is_owner(user_id: int) -> bool:
    """Check whether the Telegram user is the bot owner."""
    return user_id == OWNER_ID


def owner_only(func):
    """Restrict command handlers to the bot owner."""

    @wraps(func)
    async def wrapper(message, *args, **kwargs):

        if not message.from_user:
            return

        if not is_owner(message.from_user.id):
            logger.warning(
                "Unauthorized command attempt by user %s",
                message.from_user.id
            )

            await message.answer(
                "⛔ Access Denied!\n\n"
                "Only the Owner Admin can use this command."
            )
            return

        return await func(message, *args, **kwargs)

    return wrapper


async def check_owner(message) -> bool:
    """Reusable owner permission check."""

    if not message.from_user:
        return False

    if not is_owner(message.from_user.id):
        await message.answer(
            "⛔ You are not authorized to use this command."
        )
        return False

    return True
