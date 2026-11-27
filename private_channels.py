
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import add_channel, get_channel
from admin_permissions import has_permission


router = Router()
logger = logging.getLogger(__name__)


async def can_manage_channels(user_id: int) -> bool:
    return await has_permission(
        user_id,
        "channel_management"
    )


@router.message(Command("privatechannelhelp"))
async def private_channel_help(message: Message):

    if not message.from_user:
        return

    if not await can_manage_channels(message.from_user.id):
        await message.answer(
            "❌ Aapko channel management permission nahi hai."
        )
        return

    await message.answer(
        "🔐 PRIVATE CHANNEL ADD KARNE KA TARIKA\n\n"
        "1. Bot ko apne private channel mein Admin banayein.\n"
        "2. Private channel ka CHAT_ID hasil karein.\n"
        "3. Ye command chalayein:\n\n"
        "/addprivatechannel CHAT_ID\n\n"
        "Example:\n"
        "/addprivatechannel -1001234567890\n\n"
        "Note: Bot ko channel mein Admin hona zaroori hai."
    )


@router.message(Command("getchatid"))
async def get_chat_id_help(message: Message):

    if not message.from_user:
        return

    if not await can_manage_channels(message.from_user.id):
        await message.answer(
            "❌ Aapko permission nahi hai."
        )
        return

    await message.answer(
        "Private channel ka CHAT_ID hasil karne ke liye "
        "channel ID dekhne wale trusted Telegram bot ya "
        "Telegram API ka use karein.\n\n"
        "Uske baad command chalayein:\n"
        "/addprivatechannel CHAT_ID"
    )


@router.message(Command("addprivatechannel"))
async def add_private_channel(message: Message):

    if not message.from_user:
        return

    if not await can_manage_channels(message.from_user.id):
        await message.answer(
            "❌ Aapko channel management permission nahi hai."
        )
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "❌ Sahi format:\n"
            "/addprivatechannel CHAT_ID\n\n"
            "Example:\n"
            "/addprivatechannel -1001234567890"
        )
        return

    try:
        chat_id = int(parts[1])

    except ValueError:
        await message.answer(
            "❌ CHAT_ID number mein hona chahiye."
        )
        return

    if chat_id >= 0:
        await message.answer(
            "❌ Private channel ka CHAT_ID aam taur par "
            "negative hota hai."
        )
        return

    try:
        chat = await message.bot.get_chat(chat_id)

        if chat.type != "channel":
            await message.answer(
                "❌ Yeh Telegram channel ID nahi hai."
            )
            return

        bot_member = await message.bot.get_chat_member(
            chat_id=chat_id,
            user_id=message.bot.id
        )

        if bot_member.status not in (
            "administrator",
            "creator"
        ):
            await message.answer(
                "❌ Bot is channel ka Admin nahi hai.\n"
                "Pehle bot ko channel mein Admin banayein."
            )
            return

        existing = await get_channel(chat_id)

        if existing:
            await message.answer(
                "⚠️ Yeh channel pehle se database mein registered hai."
            )
            return

        channel = await add_channel(
            chat_id=chat_id,
            title=chat.title,
            channel_type="private",
            added_by=message.from_user.id
        )

        if not channel:
            await message.answer(
                "❌ Channel database mein add nahi ho paya.\n"
                "Railway logs check karein."
            )
            return

        await message.answer(
            "✅ PRIVATE CHANNEL ADD HO GAYA!\n\n"
            f"Name: {chat.title}\n"
            f"CHAT_ID: {chat_id}\n\n"
            "Ab channel ki quantity set kar sakte hain:\n"
            f"/setqty {chat_id} 500\n\n"
            "Automation start karne ke liye:\n"
            f"/startqty {chat_id}"
        )

        logger.info(
            "Private channel added: chat_id=%s added_by=%s",
            chat_id,
            message.from_user.id
        )

    except Exception as error:
        logger.exception(
            "Private channel registration failed: %s",
            chat_id
        )

        await message.answer(
            "❌ Channel access ya registration mein problem aayi.\n"
            "Confirm karein ki bot channel ka Admin hai.\n\n"
            f"Error: {str(error)[:300]}"
        )


logger.info("Private channels router loaded successfully.")
