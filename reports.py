
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from admin import owner_only
from database import get_report

logger = logging.getLogger(__name__)

router = Router()


async def generate_report(
    message: Message,
    hours: int,
    title: str
):
    if not await owner_only(message):
        return

    args = (message.text or "").split()

    if len(args) > 2:
        await message.answer(
            "Usage: /report24 or /report24 @channelusername"
        )
        return

    username = None

    if len(args) == 2:
        username = args[1].strip().lstrip("@").lower()

        if not username:
            await message.answer("❌ Invalid channel username.")
            return

    try:
        records = await get_report(
            hours=hours,
            channel_username=username
        )

        if not records:
            await message.answer(
                f"📊 {title}\n\nNo activity found."
            )
            return

        lines = [
            f"📊 <b>{title}</b>",
            "",
            f"Total events: {len(records)}",
        ]

        for record in records[:30]:
            channel = record["channel_username"]
            event = record["event_type"]
            quantity = record["quantity"]
            created = record["created_at"]

            lines.append(
                f"\n<b>@{channel}</b>\n"
                f"Event: {event}\n"
                f"Quantity: {quantity if quantity is not None else '-'}\n"
                f"Time: {created.strftime('%d-%m-%Y %H:%M')}"
            )

        if len(records) > 30:
            lines.append(
                f"\nShowing latest 30 of {len(records)} events."
            )

        await message.answer(
            "\n".join(lines),
            parse_mode="HTML"
        )

    except Exception:
        logger.exception("Report generation failed")
        await message.answer(
            "❌ Could not generate report. Please try again."
        )


@router.message(Command("report24"))
async def report24_command(message: Message):
    await generate_report(
        message,
        24,
        "Last 24 Hours Report"
    )


@router.message(Command("report72"))
async def report72_command(message: Message):
    await generate_report(
        message,
        72,
        "Last 72 Hours Report"
    )


@router.message(Command("reportday"))
async def reportday_command(message: Message):
    await generate_report(
        message,
        24,
        "Daily Report"
    )


@router.message(Command("reportweek"))
async def reportweek_command(message: Message):
    await generate_report(
        message,
        168,
        "Weekly Report"
    )


@router.message(Command("reportmonth"))
async def reportmonth_command(message: Message):
    await generate_report(
        message,
        720,
        "Monthly Report"
    )
