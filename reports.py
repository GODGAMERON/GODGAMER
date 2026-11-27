
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from config import TIMEZONE
from database import get_channel, get_report_summary
from admin_permissions import has_permission

router = Router()

try:
    LOCAL_TZ = ZoneInfo(TIMEZONE)
except Exception:
    LOCAL_TZ = ZoneInfo("Asia/Kolkata")


async def check_report_permission(message: Message) -> bool:
    allowed = await has_permission(
        message.from_user.id,
        "reports"
    )

    if not allowed:
        await message.answer(
            "❌ Aapko reports dekhne ki permission nahi hai."
        )
        return False

    return True


async def resolve_channel(argument: str):
    argument = argument.strip()

    if argument.startswith("@"):
        argument = argument[1:]

    try:
        numeric_id = int(argument)
        return await get_channel(numeric_id)
    except ValueError:
        return await get_channel(argument)


def format_report(data, title: str, channel_name=None) -> str:
    if not data:
        data = {}

    total_orders = data.get("total_orders", 0) or 0
    completed = data.get("completed_orders", 0) or 0
    pending = data.get("pending_orders", 0) or 0
    failed = data.get("failed_orders", 0) or 0
    total_quantity = data.get("total_quantity", 0) or 0
    total_spent = data.get("total_spent", 0) or 0

    text = (
        f"📊 {title}\n"
        "━━━━━━━━━━━━━━━━━━\n"
    )

    if channel_name:
        text += f"📢 Channel: {channel_name}\n"

    text += (
        f"🧾 Total Orders: {total_orders}\n"
        f"✅ Completed: {completed}\n"
        f"⏳ Pending: {pending}\n"
        f"❌ Failed: {failed}\n"
        f"📦 Total Quantity: {total_quantity}\n"
        f"💰 Total Spent: {total_spent}\n"
        "━━━━━━━━━━━━━━━━━━"
    )

    return text


async def send_report(
    message: Message,
    hours: int,
    title: str,
    channel_argument: str = None
):
    if not await check_report_permission(message):
        return

    channel_id = None
    channel_name = None

    if channel_argument:
        channel = await resolve_channel(channel_argument)

        if not channel:
            await message.answer("❌ Channel database mein nahi mila.")
            return

        channel_id = channel["id"]
        channel_name = (
            channel.get("title")
            or channel.get("username")
            or str(channel.get("chat_id"))
        )

    try:
        data = await get_report_summary(
            hours=hours,
            channel_id=channel_id
        )

        report_text = format_report(
            data,
            title,
            channel_name
        )

        await message.answer(report_text)

    except Exception as error:
        await message.answer(
            "❌ Report generate nahi ho payi.\n"
            f"Error: {str(error)[:300]}"
        )


@router.message(Command("report24"))
async def report_24(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    channel = parts[1] if len(parts) > 1 else None

    await send_report(
        message,
        24,
        "LAST 24 HOURS REPORT",
        channel
    )


@router.message(Command("report72"))
async def report_72(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    channel = parts[1] if len(parts) > 1 else None

    await send_report(
        message,
        72,
        "LAST 72 HOURS REPORT",
        channel
    )


@router.message(Command("reportday"))
async def report_day(message: Message):
    now = datetime.now(LOCAL_TZ)
    midnight = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    hours = max(
        1,
        int((now - midnight).total_seconds() / 3600) + 1
    )

    parts = (message.text or "").split(maxsplit=1)
    channel = parts[1] if len(parts) > 1 else None

    await send_report(
        message,
        hours,
        "TODAY REPORT",
        channel
    )


@router.message(Command("reportweek"))
async def report_week(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    channel = parts[1] if len(parts) > 1 else None

    await send_report(
        message,
        24 * 7,
        "LAST 7 DAYS REPORT",
        channel
    )


@router.message(Command("reportmonth"))
async def report_month(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    channel = parts[1] if len(parts) > 1 else None

    await send_report(
        message,
        24 * 30,
        "LAST 30 DAYS REPORT",
        channel
    )
