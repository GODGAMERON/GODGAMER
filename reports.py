
import logging
from datetime import datetime
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_report, get_channel
from admin_permissions import has_permission

router = Router()
logger = logging.getLogger(__name__)


REPORT_PERIODS = {
    "report24": (24, "Last 24 Hours"),
    "report72": (72, "Last 72 Hours"),
    "reportday": (24, "Today"),
    "reportweek": (168, "Last 7 Days"),
    "reportmonth": (720, "Last 30 Days"),
}


async def check_report_permission(message: Message) -> bool:
    if not message.from_user:
        return False

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


async def generate_report(
    message: Message,
    hours: int,
    title: str,
    channel_username: str = None
):
    try:
        channel_id = None

        if channel_username:
            channel = await get_channel(channel_username)

            if not channel:
                await message.answer(
                    "❌ Ye channel database mein nahi mila."
                )
                return

            channel_id = channel["id"]

        events = await get_report(
            hours=hours,
            channel_id=channel_id
        )

        if not events:
            await message.answer(
                f"📊 <b>{escape(title)}</b>\n\n"
                "Is period mein koi order record nahi mila.",
                parse_mode="HTML"
            )
            return

        total_orders = len(events)
        total_quantity = sum(
            int(event.get("quantity") or 0)
            for event in events
        )

        status_counts = {}

        for event in events:
            status = str(event.get("status") or "unknown").lower()
            status_counts[status] = status_counts.get(status, 0) + 1

        total_spend = sum(
            float(event.get("charge") or 0)
            for event in events
        )

        channel_text = (
            f"Channel: @{escape(channel_username)}\n"
            if channel_username
            else "Channel: All Channels\n"
        )

        report = [
            f"📊 <b>{escape(title)}</b>",
            "",
            channel_text.rstrip(),
            f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            "",
            f"📦 Total Orders: <b>{total_orders}</b>",
            f"🔢 Total Quantity: <b>{total_quantity:,}</b>",
            f"💰 Total Charge: <b>{total_spend:.4f}</b>",
            "",
            "<b>📌 ORDER STATUS</b>"
        ]

        for status, count in sorted(status_counts.items()):
            report.append(
                f"{escape(status.title())}: {count}"
            )

        report.extend([
            "",
            "━━━━━━━━━━━━━━━━━━",
            "<b>🕒 RECENT ORDERS</b>",
            "━━━━━━━━━━━━━━━━━━"
        ])

        for event in events[:15]:
            created_at = event.get("created_at")

            if created_at:
                time_text = created_at.strftime("%d-%m %H:%M")
            else:
                time_text = "Unknown"

            service_id = escape(str(event.get("service_id") or "-"))
            order_status = escape(str(event.get("status") or "unknown"))
            quantity = int(event.get("quantity") or 0)

            report.extend([
                "",
                f"Service ID: <code>{service_id}</code>",
                f"Quantity: {quantity:,}",
                f"Status: <b>{order_status}</b>",
                f"Time: {time_text}"
            ])

        await message.answer(
            "\n".join(report),
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Report generation failed")

        await message.answer(
            "❌ Report generate nahi ho saki. "
            "Railway logs check karein."
        )


def register_report_handler(
    command: str,
    hours: int,
    title: str
):
    async def handler(message: Message):

        if not await check_report_permission(message):
            return

        args = (message.text or "").split(maxsplit=1)

        if len(args) > 2:
            await message.answer(
                f"Usage:\n/{command}\n/{command} @channel"
            )
            return

        channel_username = None

        if len(args) == 2:
            username = args[1].strip()

            if username.startswith("@"):
                username = username[1:]

            username = username.rstrip("/").lower()

            if not username.replace("_", "").isalnum():
                await message.answer(
                    "❌ Invalid channel username."
                )
                return

            channel_username = username

        await generate_report(
            message=message,
            hours=hours,
            title=title,
            channel_username=channel_username
        )

    router.message.register(
        handler,
        Command(command)
    )


for command, (hours, title) in REPORT_PERIODS.items():
    register_report_handler(
        command,
        hours,
        title
    )


logger.info("Reports module loaded successfully.")
