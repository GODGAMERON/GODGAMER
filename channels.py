
import logging
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from admin import owner_only
from database import (
    add_channel,
    remove_channel,
    get_channel,
    get_all_channels,
    set_quantity,
    update_channel_status,
)

logger = logging.getLogger(__name__)

router = Router()


def clean_username(username: str) -> str:
    username = username.strip()

    if username.startswith("https://t.me/"):
        username = username.replace("https://t.me/", "", 1)
    elif username.startswith("http://t.me/"):
        username = username.replace("http://t.me/", "", 1)

    username = username.lstrip("@").strip("/")

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        raise ValueError("Invalid Telegram channel username")

    return username.lower()


@router.message(Command("addchannel"))
async def add_channel_command(message: Message):
    if not await owner_only(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/addchannel @channelusername"
        )
        return

    try:
        username = clean_username(args[1])
        result = await add_channel(username)

        if result:
            await message.answer(
                f"✅ Channel @{username} added successfully."
            )
        else:
            await message.answer(
                f"⚠️ Channel @{username} already exists."
            )

    except ValueError as error:
        await message.answer(f"❌ {error}")

    except Exception:
        logger.exception("Error while adding channel")
        await message.answer("❌ Database error while adding channel.")


@router.message(Command("removechannel"))
async def remove_channel_command(message: Message):
    if not await owner_only(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/removechannel @channelusername"
        )
        return

    try:
        username = clean_username(args[1])
        result = await remove_channel(username)

        if result:
            await message.answer(
                f"✅ Channel @{username} removed successfully."
            )
        else:
            await message.answer(
                f"⚠️ Channel @{username} was not found."
            )

    except ValueError as error:
        await message.answer(f"❌ {error}")

    except Exception:
        logger.exception("Error while removing channel")
        await message.answer("❌ Database error while removing channel.")


@router.message(Command("channels"))
async def channels_command(message: Message):
    if not await owner_only(message):
        return

    try:
        channels = await get_all_channels()

        if not channels:
            await message.answer("No channels have been added yet.")
            return

        lines = ["📋 <b>Registered Channels</b>\n"]

        for index, channel in enumerate(channels, start=1):
            status = "🟢 ON" if channel["is_active"] else "🔴 OFF"

            lines.append(
                f"{index}. @{channel['channel_username']}\n"
                f"   Quantity: {channel['quantity']}\n"
                f"   Status: {status}"
            )

        await message.answer(
            "\n\n".join(lines),
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Error while listing channels")
        await message.answer("❌ Could not fetch channels.")


@router.message(Command("setqty"))
async def set_quantity_command(message: Message):
    if not await owner_only(message):
        return

    args = (message.text or "").split()

    if len(args) != 3:
        await message.answer(
            "Usage:\n/setqty @channelusername 500"
        )
        return

    try:
        username = clean_username(args[1])
        quantity = int(args[2])

        if quantity < 0:
            raise ValueError("Quantity cannot be negative")

        result = await set_quantity(username, quantity)

        if result:
            await message.answer(
                f"✅ Quantity updated.\n"
                f"Channel: @{username}\n"
                f"Quantity: {quantity}"
            )
        else:
            await message.answer(
                f"⚠️ Channel @{username} was not found."
            )

    except ValueError as error:
        await message.answer(f"❌ {error}")

    except Exception:
        logger.exception("Error while setting quantity")
        await message.answer("❌ Database error while updating quantity.")


@router.message(Command("getqty"))
async def get_quantity_command(message: Message):
    if not await owner_only(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/getqty @channelusername"
        )
        return

    try:
        username = clean_username(args[1])
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel not found.")
            return

        await message.answer(
            f"📊 <b>Channel Quantity</b>\n\n"
            f"Channel: @{username}\n"
            f"Quantity: {channel['quantity']}\n"
            f"Status: {'🟢 ON' if channel['is_active'] else '🔴 OFF'}",
            parse_mode="HTML"
        )

    except ValueError as error:
        await message.answer(f"❌ {error}")

    except Exception:
        logger.exception("Error while getting quantity")
        await message.answer("❌ Database error while fetching quantity.")


async def change_status(message: Message, active: bool):
    if not await owner_only(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        command = "startqty" if active else "stopqty"
        await message.answer(
            f"Usage:\n/{command} @channelusername"
        )
        return

    try:
        username = clean_username(args[1])
        result = await update_channel_status(username, active)

        if not result:
            await message.answer("❌ Channel not found.")
            return

        status = "🟢 ON" if active else "🔴 OFF"

        await message.answer(
            f"✅ Channel status updated.\n"
            f"Channel: @{username}\n"
            f"Status: {status}"
        )

    except ValueError as error:
        await message.answer(f"❌ {error}")

    except Exception:
        logger.exception("Error while changing channel status")
        await message.answer("❌ Database error while updating status.")


@router.message(Command("startqty"))
async def start_quantity_command(message: Message):
    await change_status(message, True)


@router.message(Command("stopqty"))
async def stop_quantity_command(message: Message):
    await change_status(message, False)
