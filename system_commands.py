
import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_all_panels,
    get_all_channels,
    get_channel_services,
    get_panel,
)

from admin_permissions import has_permission


router = Router()
logger = logging.getLogger(__name__)


async def check_system_permission(message: Message) -> bool:
    if not message.from_user:
        return False

    allowed = await has_permission(
        message.from_user.id,
        "system_management"
    )

    if not allowed:
        await message.answer(
            "❌ Aapko System Management permission nahi hai."
        )
        return False

    return True


def panel_is_active(panel) -> bool:
    if not panel:
        return False

    return bool(
        panel.get("is_active", panel.get("active", False))
    )


def channel_name(channel) -> str:
    username = channel.get("username")

    if username:
        return "@" + str(username)

    return str(
        channel.get("title")
        or channel.get("chat_id")
        or channel.get("id")
        or "Unknown"
    )


async def send_long_message(message: Message, lines: list):
    text = ""

    for line in lines:
        if len(text) + len(line) > 3800:
            await message.answer(text)
            text = ""

        text += line + "\n"

    if text.strip():
        await message.answer(text)


# --------------------------------------------------
# PANEL STATUS
# --------------------------------------------------

@router.message(Command("panelstatus"))
async def panel_status(message: Message):

    if not await check_system_permission(message):
        return

    try:
        panels = await get_all_panels(active_only=False)

        if not panels:
            await message.answer(
                "❌ Abhi koi SMM panel add nahi hai."
            )
            return

        lines = [
            "<b>📡 SMM PANEL STATUS</b>\n"
        ]

        for panel in panels:

            panel_id = panel["id"]

            full_panel = await get_panel(panel_id)

            if not full_panel:
                lines.append(
                    f"\n⚠️ <b>{escape(str(panel['name']))}</b>\n"
                    "Panel record nahi mila."
                )
                continue

            active = panel_is_active(full_panel)

            balance = full_panel.get("last_balance")

            status = (
                "🟢 Active"
                if active
                else "🔴 Inactive"
            )

            balance_text = (
                str(balance)
                if balance is not None
                else "Not checked"
            )

            lines.append(
                f"\n<b>{escape(str(panel['name']))}</b>\n"
                f"ID: <code>{panel_id}</code>\n"
                f"Status: {status}\n"
                f"Last Balance: {escape(balance_text)}"
            )

        await send_long_message(message, lines)

    except Exception:
        logger.exception("Panel status command failed")

        await message.answer(
            "❌ Panel status check karte waqt error aaya."
        )


# --------------------------------------------------
# SERVICE HEALTH
# --------------------------------------------------

@router.message(Command("servicehealth"))
async def service_health(message: Message):

    if not await check_system_permission(message):
        return

    try:
        channels = await get_all_channels(active_only=True)

        if not channels:
            await message.answer(
                "❌ Koi active channel nahi mila."
            )
            return

        lines = [
            "<b>🩺 SERVICE HEALTH REPORT</b>\n"
        ]

        total_services = 0
        active_services = 0
        inactive_services = 0

        for channel in channels:

            services = await get_channel_services(
                channel["id"],
                active_only=False
            )

            if not services:
                continue

            lines.append(
                f"\n<b>📢 {escape(channel_name(channel))}</b>"
            )

            for service in services:

                total_services += 1

                panel = await get_panel(
                    service["panel_id"]
                )

                service_active = bool(
                    service.get("active", service.get("is_active", False))
                )

                panel_active = panel_is_active(panel)

                if service_active and panel_active:
                    active_services += 1
                    status = "🟢 Active"
                else:
                    inactive_services += 1
                    status = "🔴 Inactive"

                lines.append(
                    f"Service ID: <code>{escape(str(service['service_id']))}</code>\n"
                    f"Panel ID: <code>{service['panel_id']}</code>\n"
                    f"Status: {status}"
                )

        if total_services == 0:
            await message.answer(
                "❌ Kisi active channel par service assign nahi hai."
            )
            return

        lines.append(
            "\n<b>📊 SUMMARY</b>\n"
            f"Total Services: {total_services}\n"
            f"Active Services: {active_services}\n"
            f"Inactive Services: {inactive_services}"
        )

        await send_long_message(message, lines)

    except Exception:
        logger.exception("Service health command failed")

        await message.answer(
            "❌ Service health report banate waqt error aaya."
        )
