
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID
from database import add_channel, get_channel
from admin_permissions import has_permission

router = Router()


async def can_manage_channels(user_id: int) -> bool:
    return await has_permission(user_id, "channel_management")


@router.message(Command("privatechannelhelp"))
async def private_channel_help(message: Message):
    if not await can_manage_channels(message.from_user.id):
        await message.answer("❌ Aapko channel management permission nahi hai.")
        return

    await message.answer(
        "🔐 PRIVATE CHANNEL ADD KARNE KA TARIKA\n\n"
        "1. Bot ko apne private channel mein Admin banayein.\n"
        "2. Channel mein ek nayi post publish karein.\n"
        "3. Bot Owner ko channel ka CHAT_ID bhejega.\n"
        "4. Uske baad command chalayein:\n\n"
        "/addprivatechannel CHAT_ID\n\n"
        "Example:\n"
        "/addprivatechannel -1001234567890\n\n"
        "Note: Invite link se chat_id automatically nahi milta."
    )


@router.message(Command("getchatid"))
async def get_chat_id_help(message: Message):
    if not await can_manage_channels(message.from_user.id):
        await message.answer("❌ Permission nahi hai.")
        return

    await message.answer(
        "Bot ko private channel ka Admin banayein aur channel mein "
        "ek nayi post publish karein. Bot Owner ko channel ID bhej dega."
    )


@router.channel_post()
async def detect_private_channel(message: Message):
    chat = message.chat

    # Sirf private channels ke liye
    if chat.type != "channel" or chat.username:
        return

    # Agar channel pehle se registered hai, dobara notification na bhejein
    existing = await get_channel(chat.id)
    if existing:
        return

    bot = message.bot
    bot_member = await bot.get_chat_member(
        chat_id=chat.id,
        user_id=bot.id
    )

    if bot_member.status not in ("administrator", "creator"):
        return

    try:
        await bot.send_message(
            OWNER_ID,
            "🔐 PRIVATE CHANNEL DETECTED\n\n"
            f"Channel name: {chat.title}\n"
            f"CHAT_ID: `{chat.id}`\n\n"
            "Channel register karne ke liye command chalayein:\n"
            f"`/addprivatechannel {chat.id}`",
            parse_mode="Markdown"
        )
    except Exception:
        pass


@router.message(Command("addprivatechannel"))
async def add_private_channel(message: Message):
    if not await can_manage_channels(message.from_user.id):
        await message.answer("❌ Aapko channel management permission nahi hai.")
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
        await message.answer("❌ CHAT_ID number mein hona chahiye.")
        return

    if chat_id >= 0:
        await message.answer(
            "❌ Private channel ka CHAT_ID aam taur par negative hota hai."
        )
        return

    try:
        chat = await message.bot.get_chat(chat_id)

        if chat.type != "channel":
            await message.answer("❌ Yeh Telegram channel ID nahi hai.")
            return

        bot_member = await message.bot.get_chat_member(
            chat_id=chat_id,
            user_id=message.bot.id
        )

        if bot_member.status not in ("administrator", "creator"):
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
                "❌ Channel database mein add nahi ho paya. "
                "Database logs check karein."
            )
            return

        await message.answer(
            "✅ PRIVATE CHANNEL ADD HO GAYA!\n\n"
            f"Name: {chat.title}\n"
            f"CHAT_ID: `{chat_id}`\n\n"
            "Ab quantity set kar sakte hain:\n"
            f"/setqty {chat_id} 500\n\n"
            "Automation start karne ke liye:\n"
            f"/startqty {chat_id}",
            parse_mode="Markdown"
        )

    except Exception as error:
        await message.answer(
            "❌ Channel access nahi mil raha.\n"
            "Confirm karein ki bot channel ka Admin hai.\n\n"
            f"Error: {str(error)[:300]}"
        )
