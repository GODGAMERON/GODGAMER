
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import OWNER_ID
from database import get_all_channels, set_channel_automation
from admin_permissions import has_permission, is_owner

router = Router()


@router.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "👋 Welcome to SMM Automation Bot!\n\n"
        "Yeh bot aapke Telegram channels ki new posts par "
        "automatically configured SMM orders place karega.\n\n"
        "Commands dekhne ke liye /help bhejein.\n"
        "Apni Telegram ID dekhne ke liye /myid bhejein."
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📚 BOT COMMANDS\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "👤 BASIC\n"
        "/start\n"
        "/myid\n"
        "/admin\n"
        "/help\n"
        "/qtyhelp\n\n"
        "📢 CHANNELS\n"
        "/addchannel @channel\n"
        "/addprivatechannel CHAT_ID\n"
        "/removechannel @channel\n"
        "/channels\n"
        "/channelinfo @channel\n"
        "/startqty @channel\n"
        "/stopqty @channel\n\n"
        "📦 QUANTITY\n"
        "/setqty @channel 500\n"
        "/getqty @channel\n\n"
        "💰 SMM PANELS\n"
        "/ADDNEW\n"
        "/Allsmmpanel\n"
        "/Removesmm PANEL_ID\n"
        "/panelinfo PANEL_ID\n"
        "/checkbalance PANEL_ID\n"
        "/checkservices PANEL_ID\n\n"
        "🔧 SERVICES\n"
        "/SERVICEID @channel PanelName 5160\n"
        "/Removeserviceid @channel 5160\n"
        "/Allservicenumber\n"
        "/serviceinfo @channel\n"
        "/checkservice PANEL_ID SERVICE_ID\n\n"
        "📊 REPORTS\n"
        "/report24\n"
        "/report72\n"
        "/reportday\n"
        "/reportweek\n"
        "/reportmonth\n\n"
        "👑 ADMIN\n"
        "/Addadmin USER_ID\n"
        "/Removeadmin USER_ID\n"
        "/adminpower USER_ID\n"
        "/adminlist\n"
        "/admininfo USER_ID\n\n"
        "ℹ️ System commands ke liye Owner/Admin permissions zaroori hain."
    )


@router.message(Command("qtyhelp"))
async def quantity_help(message: Message):
    await message.answer(
        "📦 QUANTITY HELP\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Quantity set karne ke liye:\n"
        "/setqty @channel 500\n\n"
        "Current quantity check:\n"
        "/getqty @channel\n\n"
        "Automation start:\n"
        "/startqty @channel\n\n"
        "Automation stop:\n"
        "/stopqty @channel\n\n"
        "Example:\n"
        "Agar quantity 500 set hai, toh har eligible "
        "new post par har assigned service ke liye "
        "500 quantity ka order place hoga.\n\n"
        "Purane pending orders ke chalte naye posts ke "
        "orders automatically nahi rukenge."
    )


@router.message(Command("systemstatus"))
async def system_status(message: Message):
    if not await has_permission(
        message.from_user.id,
        "system_management"
    ):
        await message.answer("❌ Permission nahi hai.")
        return

    try:
        channels = await get_all_channels(active_only=False)

        active_channels = [
            channel for channel in channels
            if channel["is_active"]
        ]

        enabled_channels = [
            channel for channel in active_channels
            if channel["automation_enabled"]
        ]

        await message.answer(
            "🖥 SYSTEM STATUS\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Bot: 🟢 Running\n"
            f"Total Channels: {len(channels)}\n"
            f"Active Channels: {len(active_channels)}\n"
            f"Automation Enabled: {len(enabled_channels)}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Note: Panel health aur database health "
            "alag se verify karna hoga."
        )

    except Exception as error:
        await message.answer(
            f"❌ Status check failed: {str(error)[:300]}"
        )


@router.message(Command("autostatus"))
async def auto_status(message: Message):
    if not await has_permission(
        message.from_user.id,
        "automation_management"
    ):
        await message.answer("❌ Permission nahi hai.")
        return

    try:
        channels = await get_all_channels(active_only=False)

        if not channels:
            await message.answer("Abhi koi channel registered nahi hai.")
            return

        output = "⚙️ AUTOMATION STATUS\n━━━━━━━━━━━━━━━━━━\n"

        for channel in channels:
            name = (
                channel.get("title")
                or channel.get("username")
                or str(channel["chat_id"])
            )

            status = (
                "🟢 ON"
                if channel["automation_enabled"]
                else "🔴 OFF"
            )

            output += (
                f"\n{name}\n"
                f"Quantity: {channel['quantity']}\n"
                f"Automation: {status}\n"
                "------------------\n"
            )

        await message.answer(output[:4000])

    except Exception as error:
        await message.answer(
            f"❌ Automation status error: {str(error)[:300]}"
        )


async def set_all_automation(enabled: bool):
    channels = await get_all_channels(active_only=True)

    changed = 0

    for channel in channels:
        await set_channel_automation(
            channel["id"],
            enabled
        )
        changed += 1

    return changed


@router.message(Command("startall"))
async def start_all(message: Message):
    if not await is_owner(message.from_user.id):
        await message.answer("❌ Yeh command sirf Owner chala sakta hai.")
        return

    try:
        changed = await set_all_automation(True)

        await message.answer(
            "✅ ALL CHANNEL AUTOMATION ENABLED\n\n"
            f"Updated channels: {changed}"
        )

    except Exception as error:
        await message.answer(
            f"❌ Error: {str(error)[:300]}"
        )


@router.message(Command("stopall"))
async def stop_all(message: Message):
    if not await is_owner(message.from_user.id):
        await message.answer("❌ Yeh command sirf Owner chala sakta hai.")
        return

    try:
        changed = await set_all_automation(False)

        await message.answer(
            "🛑 ALL CHANNEL AUTOMATION STOPPED\n\n"
            f"Updated channels: {changed}\n\n"
            "Already placed SMM orders cancel nahi honge."
        )

    except Exception as error:
        await message.answer(
            f"❌ Error: {str(error)[:300]}"
        )
