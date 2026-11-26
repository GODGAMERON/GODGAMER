
import logging
import re

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    add_channel,
    get_channel,
    get_all_channels,
    remove_channel,
    set_quantity,
    set_channel_automation,
)

from admin_permissions import has_permission

logger = logging.getLogger(__name__)

router = Router()


# ==========================================
# HELPERS
# ==========================================

def clean_username(value: str):
    """Extract and validate a public Telegram channel username."""

    value = value.strip()

    value = re.sub(
        r"^https?://(www\.)?t\.me/",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = value.split("?")[0].strip("/")
    value = value.lstrip("@")

    if value.startswith("+") or value.startswith("joinchat/"):
        return None

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
        return None

    return value


async def check_permission(
    message: Message,
    permission: str
) -> bool:

    if not message.from_user:
        return False

    allowed = await has_permission(
        message.from_user.id,
        permission
    )

    if not allowed:
        await message.answer(
            "❌ Aapko is command ki permission nahi hai."
        )
        return False

    return True


# ==========================================
# ADD PUBLIC CHANNEL
# ==========================================

@router.message(Command("addchannel"))
async def add_channel_command(message: Message):

    if not await check_permission(
        message,
        "channel_management"
    ):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "❌ Command format:\n"
            "<code>/addchannel @channel</code>\n\n"
            "Example:\n"
            "<code>/addchannel @examplechannel</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer(
            "❌ Invalid public channel username.\n\n"
            "Username ya public t.me link enter karein."
        )
        return

    try:
        existing = await get_channel(username)

        if existing:
            await message.answer(
                "⚠️ Ye channel pehle se database mein added hai."
            )
            return

        # Resolve public Telegram channel information.
        chat = await message.bot.get_chat(
            f"@{username}"
        )

        if chat.type != "channel":
            await message.answer(
                "❌ Ye Telegram channel nahi hai."
            )
            return

        result = await add_channel(
            username=username,
            chat_id=chat.id,
            title=chat.title,
            channel_type="public",
            added_by=message.from_user.id
        )

        if not result:
            await message.answer(
                "❌ Channel save nahi ho saka. "
                "Ho sakta hai ye channel pehle se added ho."
            )
            return

        await message.answer(
            "✅ <b>Channel Added Successfully!</b>\n\n"
            f"📢 Channel: @{username}\n"
            f"📝 Title: {chat.title}\n"
            f"🆔 Chat ID: <code>{chat.id}</code>\n\n"
            "⚠️ Automatic post monitoring ke liye "
            "bot ko channel ka administrator banayein.",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Add channel failed")

        await message.answer(
            "❌ Channel add nahi ho saka.\n\n"
            "Check karein ki channel public hai "
            "aur Telegram username sahi hai."
        )


# ==========================================
# REMOVE CHANNEL
# ==========================================

@router.message(Command("removechannel"))
async def remove_channel_command(message: Message):

    if not await check_permission(
        message,
        "channel_management"
    ):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/removechannel @channel</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer(
            "❌ Valid channel username enter karein."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer(
                "❌ Channel database mein nahi mila."
            )
            return

        removed = await remove_channel(
            channel["id"]
        )

        if removed:
            await message.answer(
                "✅ Channel successfully deactivated.\n\n"
                "📢 Channel: @" + username + "\n\n"
                "📊 Purane orders aur reports database mein safe rahenge."
            )
        else:
            await message.answer(
                "❌ Channel deactivate nahi ho saka."
            )

    except Exception:
        logger.exception("Remove channel failed")

        await message.answer(
            "❌ Channel remove karte waqt error aaya."
        )


# ==========================================
# LIST CHANNELS
# ==========================================

@router.message(Command("channels"))
async def channels_command(message: Message):

    if not await check_permission(
        message,
        "channel_management"
    ):
        return

    try:
        channels = await get_all_channels()

        if not channels:
            await message.answer(
                "📋 Abhi koi channel add nahi hai."
            )
            return

        text = "<b>📢 CHANNEL LIST</b>\n\n"

        for index, channel in enumerate(
            channels,
            start=1
        ):

            username = (
                f"@{channel['username']}"
                if channel["username"]
                else "Private channel"
            )

            status = (
                "🟢 Active"
                if channel["is_active"]
                else "🔴 Inactive"
            )

            automation = (
                "✅ ON"
                if channel["automation_enabled"]
                else "⏸ OFF"
            )

            text += (
                f"<b>{index}. {channel['title'] or username}</b>\n"
                f"📢 {username}\n"
                f"🔢 Quantity: {channel['quantity']}\n"
                f"📌 Status: {status}\n"
                f"🤖 Automation: {automation}\n\n"
            )

        await message.answer(
            text,
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Channel list failed")

        await message.answer(
            "❌ Channel list load nahi ho saki."
        )


# ==========================================
# CHANNEL INFORMATION
# ==========================================

@router.message(Command("channelinfo"))
async def channel_info_command(message: Message):

    if not await check_permission(
        message,
        "channel_management"
    ):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/channelinfo @channel</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer(
            "❌ Invalid channel username."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer(
                "❌ Channel nahi mila."
            )
            return

        status = (
            "🟢 Active"
            if channel["is_active"]
            else "🔴 Inactive"
        )

        automation = (
            "✅ Enabled"
            if channel["automation_enabled"]
            else "⏸ Disabled"
        )

        text = (
            "<b>📢 CHANNEL INFORMATION</b>\n\n"
            f"📝 Title: {channel['title'] or 'Unknown'}\n"
            f"📢 Username: @{channel['username'] or 'Private'}\n"
            f"🆔 Chat ID: <code>{channel['chat_id'] or 'Not set'}</code>\n"
            f"📂 Type: {channel['channel_type']}\n"
            f"🔢 Quantity: {channel['quantity']}\n"
            f"📌 Status: {status}\n"
            f"🤖 Automation: {automation}"
        )

        await message.answer(
            text,
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Channel info failed")

        await message.answer(
            "❌ Channel information load nahi ho saki."
        )


# ==========================================
# SET QUANTITY
# ==========================================

@router.message(Command("setqty"))
async def set_quantity_command(message: Message):

    if not await check_permission(
        message,
        "quantity_management"
    ):
        return

    parts = (message.text or "").split()

    if len(parts) != 3:
        await message.answer(
            "❌ Command format:\n"
            "<code>/setqty @channel 500</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    try:
        quantity = int(parts[2])
    except ValueError:
        await message.answer(
            "❌ Quantity number mein enter karein."
        )
        return

    if not username or quantity <= 0:
        await message.answer(
            "❌ Valid channel aur positive quantity enter karein."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer(
                "❌ Pehle channel add karein."
            )
            return

        success = await set_quantity(
            channel["id"],
            quantity,
            changed_by=message.from_user.id
        )

        if success:
            await message.answer(
                "✅ <b>Quantity Updated!</b>\n\n"
                f"📢 Channel: @{username}\n"
                f"🔢 New Quantity: {quantity}",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Quantity update nahi ho saki."
            )

    except Exception:
        logger.exception("Set quantity failed")

        await message.answer(
            "❌ Quantity update karte waqt error aaya."
        )


# ==========================================
# GET QUANTITY
# ==========================================

@router.message(Command("getqty"))
async def get_quantity_command(message: Message):

    if not await check_permission(
        message,
        "quantity_management"
    ):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/getqty @channel</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer(
            "❌ Invalid channel username."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer(
                "❌ Channel nahi mila."
            )
            return

        await message.answer(
            f"📢 Channel: @{username}\n"
            f"🔢 Quantity: {channel['quantity']}",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Get quantity failed")

        await message.answer(
            "❌ Quantity load nahi ho saki."
        )


# ==========================================
# START AUTOMATION
# ==========================================

@router.message(Command("startqty"))
async def start_quantity_command(message: Message):

    if not await check_permission(
        message,
        "automation_management"
    ):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/startqty @channel</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer(
            "❌ Invalid channel username."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer(
                "❌ Channel nahi mila."
            )
            return

        if not channel["is_active"]:
            await message.answer(
                "❌ Ye channel inactive hai. Pehle ise active karein."
            )
            return

        if channel["quantity"] <= 0:
            await message.answer(
                "❌ Pehle channel ki quantity set karein."
            )
            return

        success = await set_channel_automation(
            channel["id"],
            True
        )

        if success:
            await message.answer(
                "✅ <b>Automation Enabled!</b>\n\n"
                f"📢 Channel: @{username}\n"
                f"🔢 Quantity: {channel['quantity']}\n\n"
                "Naye posts par automatic orders ke liye "
                "channel service configure hona bhi zaroori hai.",
                parse_mode="HTML"
            )

    except Exception:
        logger.exception("Start automation failed")

        await message.answer(
            "❌ Automation start nahi ho saki."
        )


# ==========================================
# STOP AUTOMATION
# ==========================================

@router.message(Command("stopqty"))
async def stop_quantity_command(message: Message):

    if not await check_permission(
        message,
        "automation_management"
    ):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "<code>/stopqty @channel</code>",
            parse_mode="HTML"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer(
            "❌ Invalid channel username."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer(
                "❌ Channel nahi mila."
            )
            return

        success = await set_channel_automation(
            channel["id"],
            False
        )

        if success:
            await message.answer(
                "⏸ <b>Automation Disabled!</b>\n\n"
                f"📢 Channel: @{username}\n\n"
                "Naye posts par automatic orders nahi lagenge. "
                "Pehle se placed orders panel par apne status ke "
                "according continue rahenge.",
                parse_mode="HTML"
            )

    except Exception:
        logger.exception("Stop automation failed")

        await message.answer(
            "❌ Automation stop nahi ho saki."
        )


logger.info("Channel management module loaded.")
