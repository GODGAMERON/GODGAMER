
import logging
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from admin import check_owner
from database import (
    add_channel,
    remove_channel,
    get_channel,
    get_all_channels,
    set_quantity,
    update_channel_status
)

router = Router()
logger = logging.getLogger(name)


def normalize_channel(value):
    """Validate and normalize a Telegram channel username."""

    username = value.strip()

    username = re.sub(
        r"^https?://(www\.)?t\.me/",
        "",
        username
    )

    username = username.lstrip("@").rstrip("/")

    if not re.fullmatch(r"[a-zA-Z0-9_]{5,32}", username):
        return None

    return username.lower()


@router.message(Command("addchannel"))
async def add_channel_command(message: Message):

    if not await check_owner(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/addchannel @channel"
        )
        return

    username = normalize_channel(args[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        result = await add_channel(username)

        if result:
            await message.answer(
                f"✅ Channel Added Successfully!\n\n"
                f"Channel: @{username}\n"
                f"Quantity: 0\n"
                f"Status: OFF"
            )
        else:
            await message.answer(
                "⚠️ This channel is already registered."
            )

    except Exception:
        logger.exception("Add channel failed")
        await message.answer("❌ Database error while adding channel.")


@router.message(Command("removechannel"))
async def remove_channel_command(message: Message):

    if not await check_owner(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/removechannel @channel"
        )
        return

    username = normalize_channel(args[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        result = await remove_channel(username)

        if result:
            await message.answer(
                f"✅ Channel Removed!\n\n@{username}"
            )
        else:
            await message.answer(
                "❌ Channel not found in database."
            )

    except Exception:
        logger.exception("Remove channel failed")
        await message.answer("❌ Database error.")


@router.message(Command("channels"))
async def channels_command(message: Message):

    if not await check_owner(message):
        return

    try:
        channels = await get_all_channels()

        if not channels:
            await message.answer(
                "📭 No channels registered yet."
            )
            return

        response = "📊 REGISTERED CHANNELS\n\n"

        for index, channel in enumerate(channels, 1):

            status = (
                "🟢 ON"
                if channel["is_active"]
                else "🔴 OFF"
            )

            response += (
                f"{index}. @{channel['channel_username']}\n"
                f"Quantity: {channel['quantity']}\n"
                f"Status: {status}\n\n"
            )

        await message.answer(response)

    except Exception:
        logger.exception("Channels list failed")
        await message.answer("❌ Unable to fetch channels.")


@router.message(Command("setqty"))
async def set_quantity_command(message: Message):

    if not await check_owner(message):
        return

    args = (message.text or "").split()

    if len(args) != 3:
        await message.answer(
            "Usage:\n/setqty @channel 500"
        )
        return

    username = normalize_channel(args[1])

    try:
        quantity = int(args[2])

        if quantity < 0:
            raise ValueError

except ValueError:
        await message.answer(
            "❌ Quantity must be a non-negative number."
        )
        return

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        result = await set_quantity(username, quantity)

        if result:
            await message.answer(
                f"✅ Quantity Updated!\n\n"
                f"Channel: @{username}\n"
                f"Quantity: {quantity}\n"
                f"Status: {'ON' if result['is_active'] else 'OFF'}"
            )
        else:
            await message.answer(
                "❌ Channel not found.\n"
                "Use /addchannel first."
            )

    except Exception:
        logger.exception("Set quantity failed")
        await message.answer("❌ Database error.")


@router.message(Command("getqty"))
async def get_quantity_command(message: Message):

    if not await check_owner(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/getqty @channel"
        )
        return

    username = normalize_channel(args[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel not found.")
            return

        status = (
            "🟢 ON"
            if channel["is_active"]
            else "🔴 OFF"
        )

        await message.answer(
            f"📊 CHANNEL STATUS\n\n"
            f"Channel: @{username}\n"
            f"Quantity: {channel['quantity']}\n"
            f"Status: {status}\n"
            f"Created: {channel['created_at']}"
        )

    except Exception:
        logger.exception("Get quantity failed")
        await message.answer("❌ Database error.")


@router.message(Command("startqty"))
async def start_quantity_command(message: Message):

    if not await check_owner(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/startqty @channel"
        )
        return

    username = normalize_channel(args[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        result = await update_channel_status(
            username,
            True
        )

        if result:
            await message.answer(
                f"🟢 Channel Service Enabled!\n\n"
                f"Channel: @{username}\n"
                f"Quantity: {result['quantity']}"
            )
        else:
            await message.answer("❌ Channel not found.")

    except Exception:
        logger.exception("Start quantity failed")
        await message.answer("❌ Database error.")


@router.message(Command("stopqty"))
async def stop_quantity_command(message: Message):

    if not await check_owner(message):
        return

    args = (message.text or "").split()

    if len(args) != 2:
        await message.answer(
            "Usage:\n/stopqty @channel"
        )
        return

    username = normalize_channel(args[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        result = await update_channel_status(
            username,
            False
        )

        if result:
            await message.answer(
                f"🔴 Channel Service Disabled!\n\n"
                f"Channel: @{username}"
            )
        else:
            await message.answer("❌ Channel not found.")

    except Exception:
        logger.exception("Stop quantity failed")
        await message.answer("❌ Database error.")
