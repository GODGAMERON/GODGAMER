
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_all_channels, set_channel_automation
from admin_permissions import has_permission, is_owner

router = Router()
logger = logging.getLogger(__name__)


def get_user_id(message: Message):
    return message.from_user.id if message.from_user else None


async def check_permission(message: Message, permission: str) -> bool:
    user_id = get_user_id(message)

    if user_id is None:
        return False

    if not await has_permission(user_id, permission):
        await message.answer("❌ Aapko is command ki permission nahi hai.")
        return False

    return True


@router.message(Command("start"))
async def start_command(message: Message):
    await message.answer(
        "👋 Welcome to SMM Automation Bot!\n\n"
        "Yeh bot aapke Telegram channels ki new posts par "
        "configured SMM orders automatically place karega.\n\n"
        "Commands ke liye /help bhejein.\n"
        "Apni Telegram ID ke liye /myid bhejein."
    )


@router.message(Command("myid"))
async def my_id_command(message: Message):
    user_id = get_user_id(message)

    if user_id is None:
        return

    await message.answer(
        f"🆔 Your Telegram ID:\n<code>{user_id}</code>",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "📚 <b>BOT COMMANDS</b>\n"
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
        "📦 ORDERS\n"
        "/orders\n"
        "/pendingorders\n"
        "/orderinfo ORDER_ID\n"
        "/checkorder ORDER_ID\n"
        "/cancelorder ORDER_ID\n\n"
        "⚙️ AUTOMATION\n"
        "/autostatus\n"
        "/startall\n"
        "/stopall\n\n"
        "🖥 SYSTEM\n"
        "/systemstatus\n\n"
        "👑 ADMIN\n"
        "/Addadmin USER_ID\n"
        "/Removeadmin USER_ID\n"
        "/adminpower USER_ID\n"
        "/adminlist\n"
        "/admininfo USER_ID\n\n"
        "Note: Commands permission ke according hi work karenge.",
        parse_mode="HTML"
    )


@router.message(Command("qtyhelp"))
async def quantity_help(message: Message):
    await message.answer(
        "📦 <b>QUANTITY HELP</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "Quantity set:\n"
        "/setqty @channel 500\n\n"
        "Quantity check:\n"
        "/getqty @channel\n\n"
        "Automation start:\n"
        "/startqty @channel\n\n"
        "Automation stop:\n"
        "/stopqty @channel\n\n"
        "Agar quantity 500 set hai, toh har eligible "
        "new post par har assigned service ke liye "
        "configured quantity ka order place hoga.\n\n"
        "Pending orders naye posts ke orders ko block nahi karte.",
        parse_mode="HTML"
    )


@router.message(Command("systemstatus"))
async def system_status(message: Message):
    if not await check_permission(message, "system_management"):
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
            "🖥 <b>SYSTEM STATUS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Bot: 🟢 Running\n"
            f"Total Channels: {len(channels)}\n"
            f"Active Channels: {len(active_channels)}\n"
            f"Automation Enabled: {len(enabled_channels)}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Panel health aur database health alag se verify karein.",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("System status command failed.")
        await message.answer("❌ System status check failed.")


@router.message(Command("autostatus"))
async def auto_status(message: Message):
    if not await check_permission(message, "automation_management"):
        return

    try:
        channels = await get_all_channels(active_only=False)

        if not channels:
            await message.answer("Abhi koi channel registered nahi hai.")
            return

        output = "<b>⚙️ AUTOMATION STATUS</b>\n━━━━━━━━━━━━━━━━━━\n"

        for channel in channels:
            name = (
                channel.get("title")
                or channel.get("username")
                or str(channel.get("chat_id") or channel["id"])
            )

            status = "🟢 ON" if channel["automation_enabled"] else "🔴 OFF"
            active = "Active" if channel["is_active"] else "Inactive"

            output += (
                f"\n<b>{name}</b>\n"
                f"Channel status: {active}\n"
                f"Quantity: {channel['quantity']}\n"
                f"Automation: {status}\n"
                "━━━━━━━━━━━━━━━━━━\n"
            )

        await message.answer(output[:4000], parse_mode="HTML")

    except Exception:
        logger.exception("Automation status command failed.")
        await message.answer("❌ Automation status load nahi ho saka.")


async def set_all_automation(enabled: bool):
    # Start only active channels. Stop automation on every channel.
    channels = await get_all_channels(
        active_only=enabled
    )

    changed = 0
    failed = 0

    for channel in channels:
        try:
            success = await set_channel_automation(
                channel["id"],
                enabled
            )

            if success:
                changed += 1
            else:
                failed += 1

        except Exception:
            failed += 1
            logger.exception(
                "Bulk automation update failed for channel %s",
                channel["id"]
            )

    return changed, failed


@router.message(Command("startall"))
async def start_all(message: Message):
    user_id = get_user_id(message)

    if user_id is None or not is_owner(user_id):
        await message.answer("❌ Yeh command sirf Owner chala sakta hai.")
        return

    try:
        changed, failed = await set_all_automation(True)

        await message.answer(
            "✅ <b>ACTIVE CHANNEL AUTOMATION ENABLED</b>\n\n"
            f"Updated channels: {changed}\n"
            f"Failed: {failed}\n\n"
            "Note: Channel par service aur valid quantity configured honi chahiye.",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Start all automation failed.")
        await message.answer("❌ Automation enable nahi ho saki.")


@router.message(Command("stopall"))
async def stop_all(message: Message):
    user_id = get_user_id(message)

    if user_id is None or not is_owner(user_id):
        await message.answer("❌ Yeh command sirf Owner chala sakta hai.")
        return

    try:
        changed, failed = await set_all_automation(False)

        await message.answer(
            "🛑 <b>ALL CHANNEL AUTOMATION STOPPED</b>\n\n"
            f"Updated channels: {changed}\n"
            f"Failed: {failed}\n\n"
            "Already placed SMM orders cancel nahi honge.",
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Stop all automation failed.")
        await message.answer("❌ Automation stop nahi ho saki.")


logger.info("Bot commands module loaded successfully.")
