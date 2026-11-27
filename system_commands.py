
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


async def check_system_permission(message: Message) -> bool:
    if not message.from_user:
        return False

    allowed = await has_permission(
        message.from_user.id,
        "system_management"
    )

    if not allowed:
        await message.answer(
            "❌ Aapko ye command use karne ki permission nahi hai."
        )
        return False

    return True


@router.message(Command("panelstatus"))
async def panel_status(message: Message):
    if not await check_system_permission(message):
        return

    panels = await get_all_panels(active_only=False)

    if not panels:
        await message.answer("❌ Abhi koi SMM panel add nahi hai.")
        return

    lines = ["<b>📡 SMM PANEL STATUS</b>\n"]

    for panel in panels:
        panel_id = panel["id"]

        full_panel = await get_panel(panel_id)

        if not full_panel:
            lines.append(
                f"⚠️ <b>{panel['name']}</b>\n"
                "Status: Panel record nahi mila\n"
            )
            continue

        active = full_panel.get("active", panel.get("is_active", False))
        balance = full_panel.get("last_balance")

        status = "🟢 Active" if active else "🔴 Inactive"

        balance_text = (
            str(balance) if balance is not None else "Not checked"
        )

        lines.append(
            f"<b>{panel['name']}</b>\n"
            f"ID: <code>{panel_id}</code>\n"
            f"Status: {status}\n"
            f"Last Balance: {balance_text}\n"
        )

    await message.answer("\n".join(lines))


@router.message(Command("servicehealth"))
async def service_health(message: Message):
    if not await check_system_permission(message):
        return

    channels = await get_all_channels(active_only=True)

    if not channels:
        await message.answer("❌ Koi active channel nahi mila.")
        return

    lines = ["<b>🩺 SERVICE HEALTH REPORT</b>\n"]

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

        channel_name = (
            f"@{channel['username']}"
            if channel.get("username")
            else channel.get("title") or str(channel["chat_id"])
        )

        lines.append(f"\n<b>📢 {channel_name}</b>")

        for service in services:
            total_services += 1

            panel = await get_panel(service["panel_id"])

            service_active = service.get("active", service.get("is_active", False))
            panel_active = (
                panel.get("active", panel.get("is_active", False)) if panel else False
            )

            if service_active and panel_active:
                active_services += 1
                status = "🟢 Active"
            else:
                inactive_services += 1
                status = "🔴 Inactive"

            lines.append(
                f"Service ID: <code>{service['service_id']}</code>\n"
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

    await message.answer("\n".join(lines))


