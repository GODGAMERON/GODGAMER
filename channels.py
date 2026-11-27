
import logging
import re
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database import (
    add_channel,
    get_channel,
    get_all_channels,
    remove_channel,
    set_quantity,
    set_channel_automation,
    update_channel_status,
)

from admin_permissions import has_permission

router = Router()
logger = logging.getLogger(__name__)


# ==========================================
# HELPERS
# ==========================================

def clean_username(value: str):
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


async def check_permission(message: Message, permission: str) -> bool:
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


def channel_status_keyboard(channel_id: int, is_active: bool):
    if is_active:
        button_text = "🔴 Make Inactive"
        new_status = 0
    else:
        button_text = "🟢 Make Active"
        new_status = 1

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"channel_status:{channel_id}:{new_status}"
                )
            ]
        ]
    )


# ==========================================
# ADD PUBLIC CHANNEL
# ==========================================

@router.message(Command("addchannel"))
async def add_channel_command(message: Message):

    if not await check_permission(message, "channel_management"):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Command format:\n"
            "/addchannel @channel"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        existing = await get_channel(username)

        if existing:
            await message.answer(
                "⚠️ Ye channel pehle se database mein added hai."
            )
            return

        chat = await message.bot.get_chat(f"@{username}")

        if chat.type != "channel":
            await message.answer("❌ Ye Telegram channel nahi hai.")
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
                "❌ Channel database mein save nahi ho saka."
            )
            return

        await message.answer(
            "✅ <b>CHANNEL ADDED SUCCESSFULLY</b>\n\n"
            f"📢 Channel: @{escape(username)}\n"
            f"📝 Title: {escape(chat.title or 'Unknown')}\n"
            f"🆔 Chat ID: <code>{chat.id}</code>\n"
            "📌 Status: 🟢 Active\n"
            "🤖 Automation: ⏸ OFF\n\n"
            "Automation start karne ke liye /startqty use karein.\n"
            "Bot ko channel ka administrator banana zaroori hai.",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Add channel failed.")
        await message.answer(
            "❌ Channel add nahi ho saka. "
            "Username aur bot permissions check karein."
        )


# ==========================================
# REMOVE CHANNEL
# ==========================================

@router.message(Command("removechannel"))
async def remove_channel_command(message: Message):

    if not await check_permission(message, "channel_management"):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Format:\n/removechannel @channel"
        )
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel nahi mila.")
            return

        removed = await remove_channel(channel["id"])

        if removed:
            await message.answer(
                f"✅ Channel deactivate kar diya gaya.\n\n@{escape(username)}\n\n"
                "Purane orders aur reports database mein safe rahenge.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Channel deactivate nahi ho saka.")

    except Exception:
        logger.exception("Remove channel failed.")
        await message.answer("❌ Channel remove karte waqt error aaya.")


# ==========================================
# LIST CHANNELS WITH INLINE STATUS BUTTONS
# ==========================================

@router.message(Command("channels"))
async def channels_command(message: Message):

    if not await check_permission(message, "channel_management"):
        return

    try:
        channels = await get_all_channels(active_only=False)

        if not channels:
            await message.answer("📋 Abhi koi channel add nahi hai.")
            return

        for index, channel in enumerate(channels, start=1):

            username = (
                f"@{channel['username']}"
                if channel.get("username")
                else "Private channel"
            )

            title = escape(
                channel.get("title") or username
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

            text = (
                f"<b>{index}. {title}</b>\n"
                f"📢 {escape(username)}\n"
                f"🆔 ID: <code>{channel.get('chat_id') or 'N/A'}</code>\n"
                f"🔢 Quantity: {channel['quantity']}\n"
                f"📌 Status: {status}\n"
                f"🤖 Automation: {automation}"
            )

            await message.answer(
                text,
                reply_markup=channel_status_keyboard(
                    channel["id"],
                    channel["is_active"]
                ),
                parse_mode="HTML"
            )

    except Exception:
        logger.exception("Channel list failed.")
        await message.answer("❌ Channel list load nahi ho saki.")


# ==========================================
# INLINE ACTIVE / INACTIVE BUTTON
# ==========================================

@router.callback_query(lambda query: (
    query.data or ""
).startswith("channel_status:"))
async def change_channel_status(callback: CallbackQuery):

    if not callback.from_user:
        await callback.answer("User identify nahi hua.", show_alert=True)
        return

    allowed = await has_permission(
        callback.from_user.id,
        "channel_management"
    )

    if not allowed:
        await callback.answer(
            "❌ Aapko channel management permission nahi hai.",
            show_alert=True
        )
        return

    try:
        parts = (callback.data or "").split(":")

        if len(parts) != 3:
            await callback.answer("Invalid button data.", show_alert=True)
            return

        channel_id = int(parts[1])
        new_status = int(parts[2])

        if new_status not in (0, 1):
            await callback.answer("Invalid status.", show_alert=True)
            return

        channel = await get_channel(channel_id)

        if not channel:
            await callback.answer(
                "Channel database mein nahi mila.",
                show_alert=True
            )
            return

        success = await update_channel_status(
            channel_id,
            bool(new_status)
        )

        if not success:
            await callback.answer(
                "Channel status update nahi hua.",
                show_alert=True
            )
            return

        # Inactive channel ki automation bhi band kar dein.
        if not new_status:
            await set_channel_automation(
                channel_id,
                False
            )

        updated_channel = await get_channel(channel_id)

        username = (
            f"@{updated_channel['username']}"
            if updated_channel.get("username")
            else "Private channel"
        )

        status = (
            "🟢 Active"
            if updated_channel["is_active"]
            else "🔴 Inactive"
        )

        automation = (
            "✅ ON"
            if updated_channel["automation_enabled"]
            else "⏸ OFF"
        )

        title = escape(
            updated_channel.get("title") or username
        )

        text = (
            f"<b>📢 {title}</b>\n"
            f"📢 {escape(username)}\n"
            f"🆔 ID: <code>{updated_channel.get('chat_id') or 'N/A'}</code>\n"
            f"🔢 Quantity: {updated_channel['quantity']}\n"
            f"📌 Status: {status}\n"
            f"🤖 Automation: {automation}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=channel_status_keyboard(
                channel_id,
                bool(new_status)
            ),
            parse_mode="HTML"
        )

        await callback.answer(
            "✅ Channel status updated."
        )

    except Exception:
        logger.exception("Channel status button failed.")
        await callback.answer(
            "❌ Status update mein error aaya.",
            show_alert=True
        )


# ==========================================
# CHANNEL INFORMATION
# ==========================================

@router.message(Command("channelinfo"))
async def channel_info_command(message: Message):

    if not await check_permission(message, "channel_management"):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Format:\n/channelinfo @channel")
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel nahi mila.")
            return

        status = "🟢 Active" if channel["is_active"] else "🔴 Inactive"
        automation = (
            "✅ Enabled"
            if channel["automation_enabled"]
            else "⏸ Disabled"
        )

        await message.answer(
            "<b>📢 CHANNEL INFORMATION</b>\n\n"
            f"📝 Title: {escape(channel.get('title') or 'Unknown')}\n"
            f"📢 Username: {escape(username)}\n"
            f"🆔 Chat ID: <code>{channel.get('chat_id') or 'N/A'}</code>\n"
            f"📂 Type: {escape(channel['channel_type'])}\n"
            f"🔢 Quantity: {channel['quantity']}\n"
            f"📌 Status: {status}\n"
            f"🤖 Automation: {automation}",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Channel info failed.")
        await message.answer("❌ Channel information load nahi ho saki.")


# ==========================================
# SET QUANTITY
# ==========================================

@router.message(Command("setqty"))
async def set_quantity_command(message: Message):

    if not await check_permission(message, "quantity_management"):
        return

    parts = (message.text or "").split()

    if len(parts) != 3:
        await message.answer(
            "Format:\n/setqty @channel 500"
        )
        return

    username = clean_username(parts[1])

    try:
        quantity = int(parts[2])
    except ValueError:
        await message.answer("❌ Quantity number mein enter karein.")
        return

    if not username or quantity <= 0:
        await message.answer(
            "❌ Valid channel aur positive quantity enter karein."
        )
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Pehle channel add karein.")
            return

        success = await set_quantity(
            channel["id"],
            quantity,
            changed_by=message.from_user.id
        )

        if success:
            await message.answer(
                "✅ Quantity updated!\n\n"
                f"Channel: @{escape(username)}\n"
                f"New quantity: {quantity}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Quantity update nahi ho saki.")

    except Exception:
        logger.exception("Set quantity failed.")
        await message.answer("❌ Quantity update karte waqt error aaya.")


# ==========================================
# GET QUANTITY
# ==========================================

@router.message(Command("getqty"))
async def get_quantity_command(message: Message):

    if not await check_permission(message, "quantity_management"):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Format:\n/getqty @channel")
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel nahi mila.")
            return

        await message.answer(
            f"📢 Channel: @{escape(username)}\n"
            f"🔢 Quantity: {channel['quantity']}",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Get quantity failed.")
        await message.answer("❌ Quantity load nahi ho saki.")


# ==========================================
# START AUTOMATION
# ==========================================

@router.message(Command("startqty"))
async def start_quantity_command(message: Message):

    if not await check_permission(message, "automation_management"):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Format:\n/startqty @channel")
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel nahi mila.")
            return

        if not channel["is_active"]:
            await message.answer(
                "❌ Channel inactive hai. Pehle /channels mein Active karein."
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
                "✅ Automation enabled!\n\n"
                f"Channel: @{escape(username)}\n"
                f"Quantity: {channel['quantity']}\n\n"
                "Assigned service hona bhi zaroori hai.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Automation enable nahi hui.")

    except Exception:
        logger.exception("Start automation failed.")
        await message.answer("❌ Automation start nahi ho saki.")


# ==========================================
# STOP AUTOMATION
# ==========================================

@router.message(Command("stopqty"))
async def stop_quantity_command(message: Message):

    if not await check_permission(message, "automation_management"):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Format:\n/stopqty @channel")
        return

    username = clean_username(parts[1])

    if not username:
        await message.answer("❌ Invalid channel username.")
        return

    try:
        channel = await get_channel(username)

        if not channel:
            await message.answer("❌ Channel nahi mila.")
            return

        success = await set_channel_automation(
            channel["id"],
            False
        )

        if success:
            await message.answer(
                "⏸ Automation disabled.\n\n"
                f"Channel: @{escape(username)}\n\n"
                "Already placed SMM orders cancel nahi honge.",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Automation stop nahi hui.")

    except Exception:
        logger.exception("Stop automation failed.")
        await message.answer("❌ Automation stop nahi ho saki.")


logger.info("Channel management module loaded successfully.")

