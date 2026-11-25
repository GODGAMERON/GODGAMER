
import logging

from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from admin import check_owner
from database import get_report

router = Router()
logger = logging.getLogger(name)


REPORT_PERIODS = {
    "report24": (24, "Last 24 Hours"),
    "report72": (72, "Last 72 Hours"),
    "reportday": (24, "Today"),
    "reportweek": (168, "Last 7 Days"),
    "reportmonth": (720, "Last 30 Days"),
}


async def generate_report(
    message: Message,
    hours: int,
    title: str,
    channel_username: str = None
):
    """Generate channel activity report."""

    try:
        events = await get_report(
            hours=hours,
            channel_username=channel_username
        )

        if not events:
            await message.answer(
                f"📊 {title}\n\n"
                "No activity records found."
            )
            return

        total_events = len(events)
        set_events = 0
        start_events = 0
        stop_events = 0
        add_events = 0
        remove_events = 0

        latest_events = events[:15]

        for event in events:
            event_type = event["event_type"]

            if event_type == "SET_QUANTITY":
                set_events += 1

            elif event_type == "START":
                start_events += 1

            elif event_type == "STOP":
                stop_events += 1

            elif event_type == "ADD_CHANNEL":
                add_events += 1

            elif event_type == "REMOVE_CHANNEL":
                remove_events += 1

        channel_text = (
            f"Channel: @{channel_username}\n"
            if channel_username else
            "Channel: All Channels\n"
        )

        report = (
            f"📊 {title}\n\n"
            f"{channel_text}"
            f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}\n\n"
            f"📌 TOTAL EVENTS: {total_events}\n"
            f"➕ Channels Added: {add_events}\n"
            f"➖ Channels Removed: {remove_events}\n"
            f"🔢 Quantity Updates: {set_events}\n"
            f"🟢 Services Started: {start_events}\n"
            f"🔴 Services Stopped: {stop_events}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"RECENT ACTIVITY\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )

        for event in latest_events:
            event_time = event["created_at"].strftime(
                "%d-%m %H:%M"
            )

            report += (
                f"\n@{event['channel_username']}\n"
                f"Action: {event['event_type']}\n"
                f"Quantity: {event['quantity']}\n"
                f"Time: {event_time}\n"
            )

        await message.answer(report)

    except Exception:
        logger.exception("Report generation failed")
        await message.answer(
            "❌ Unable to generate report."
        )


def register_report_handler(
    command: str,
    hours: int,
    title: str
):
    """Register overall and single-channel report commands."""

    async def handler(message: Message):

        if not await check_owner(message):
            return

        args = (message.text or "").split()

        if len(args) > 2:
            await message.answer(
                f"Usage:\n/{command}\n"
                f"/{command} @channel"
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
            message,
            hours,
            title,
            channel_username
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
