
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_channel,
    get_panel_by_name,
    get_panel,
    add_channel_service,
    get_channel_services,
    remove_channel_service,
    get_all_channels,
)

from admin_permissions import has_permission
from smm_api import get_panel_services


router = Router()
logger = logging.getLogger(__name__)


async def service_permission(message: Message) -> bool:

    if not message.from_user:
        return False

    allowed = await has_permission(
        message.from_user.id,
        "service_management"
    )

    if not allowed:
        await message.answer(
            "❌ Aapko Service Management permission nahi hai."
        )
        return False

    return True


def panel_is_active(panel):

    if not panel:
        return False

    return bool(
        panel.get("active", panel.get("is_active", False))
    )


async def find_channel(identifier: str):

    identifier = identifier.strip()

    if identifier.startswith("@"):
        identifier = identifier[1:]

    try:
        return await get_channel(int(identifier))

    except ValueError:
        return await get_channel(identifier)


async def find_panel_service(panel, service_id):

    services = await get_panel_services(
        panel["api_url"],
        panel["api_key"]
    )

    return next(
        (
            item for item in services
            if str(item.get("service")) == str(service_id)
        ),
        None
    )


@router.message(Command("SERVICEID"))
async def assign_service(message: Message):

    if not await service_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 4:
        await message.answer(
            "❌ Sahi format:\n\n"
            "/SERVICEID @channel PanelName SERVICE_ID\n\n"
            "Example:\n"
            "/SERVICEID @example PanelOne 5160\n\n"
            "Private channel ke liye:\n"
            "/SERVICEID -1001234567890 PanelOne 5160"
        )
        return

    channel_identifier = parts[1]
    panel_name = parts[2]

    try:
        service_id = int(parts[3])

        if service_id <= 0:
            raise ValueError

    except ValueError:
        await message.answer(
            "❌ Service ID positive number hona chahiye."
        )
        return

    try:
        channel = await find_channel(channel_identifier)

        if not channel:
            await message.answer(
                "❌ Channel registered nahi hai.\n"
                "Pehle /addchannel ya /addprivatechannel karein."
            )
            return

        if not channel.get("is_active"):
            await message.answer(
                "❌ Yeh channel inactive hai."
            )
            return

        panel = await get_panel_by_name(panel_name)

        if not panel or not panel_is_active(panel):
            await message.answer(
                "❌ Panel nahi mila ya inactive hai."
            )
            return

        selected_service = await find_panel_service(
            panel,
            service_id
        )

        if not selected_service:
            await message.answer(
                f"❌ Service ID {service_id} "
                "is panel par nahi mili."
            )
            return

        result = await add_channel_service(
            channel_id=channel["id"],
            panel_id=panel["id"],
            service_id=service_id,
            service_name=selected_service.get(
                "name",
                "Unknown"
            )
        )

        if not result:
            await message.answer(
                "❌ Service assign nahi ho payi."
            )
            return

        channel_name = (
            channel.get("title")
            or channel.get("username")
            or str(channel["chat_id"])
        )

        await message.answer(
            "✅ SERVICE ASSIGNED!\n\n"
            f"Channel: {channel_name}\n"
            f"Panel: {panel['name']}\n"
            f"Service ID: {service_id}\n"
            f"Service: {selected_service.get('name', 'Unknown')}\n\n"
            "Ab is channel ki new posts par "
            "yeh service use ki ja sakti hai."
        )

        logger.info(
            "Service assigned: channel=%s panel=%s service=%s",
            channel["id"],
            panel["id"],
            service_id
        )

    except Exception as error:
        logger.exception("Service assignment failed")

        await message.answer(
            "❌ Service assignment error:\n"
            f"{str(error)[:300]}"
        )


@router.message(Command("Removeserviceid"))
async def remove_service(message: Message):

    if not await service_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 3:
        await message.answer(
            "Format:\n"
            "/Removeserviceid @channel SERVICE_ID\n\n"
            "Private channel:\n"
            "/Removeserviceid -1001234567890 SERVICE_ID"
        )
        return

    channel = await find_channel(parts[1])

    if not channel:
        await message.answer(
            "❌ Channel nahi mila."
        )
        return

    try:
        service_id = int(parts[2])

        if service_id <= 0:
            raise ValueError

        result = await remove_channel_service(
            channel_id=channel["id"],
            service_id=service_id
        )

        if result:
            await message.answer(
                f"✅ Service {service_id} "
                "channel se remove kar di gayi."
            )
        else:
            await message.answer(
                "❌ Service nahi mili ya pehle se inactive hai."
            )

    except ValueError:
        await message.answer(
            "❌ Service ID positive number mein bhejein."
        )

    except Exception as error:
        logger.exception("Service removal failed")

        await message.answer(
            f"❌ Error: {str(error)[:300]}"
        )


@router.message(Command("Allservicenumber"))
async def all_services(message: Message):

    if not await service_permission(message):
        return

    try:
        channels = await get_all_channels(
            active_only=True
        )

        if not channels:
            await message.answer(
                "Abhi koi active channel nahi hai."
            )
            return

        output = (
            "📋 ALL ASSIGNED SERVICES\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

        count = 0

        for channel in channels:

            services = await get_channel_services(
                channel["id"]
            )

            if not services:
                continue

            channel_name = (
                channel.get("title")
                or channel.get("username")
                or str(channel["chat_id"])
            )

            for service in services:

                count += 1

                output += (
                    f"\nChannel: {channel_name}\n"
                    f"Panel ID: {service['panel_id']}\n"
                    f"Service ID: {service['service_id']}\n"
                    f"Service: {service.get('service_name') or 'Unknown'}\n"
                    "------------------\n"
                )

                if len(output) > 3500:
                    await message.answer(output)
                    output = ""

        if count == 0:
            await message.answer(
                "Koi service assign nahi hai."
            )

        elif output:
            await message.answer(output)

    except Exception as error:
        logger.exception("Assigned service list failed")

        await message.answer(
            f"❌ Service list error: {str(error)[:300]}"
        )


@router.message(Command("serviceinfo"))
async def service_info(message: Message):

    if not await service_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/serviceinfo @channel\n\n"
            "Private channel:\n/serviceinfo -1001234567890"
        )
        return

    channel = await find_channel(parts[1])

    if not channel:
        await message.answer(
            "❌ Channel nahi mila."
        )
        return

    try:
        services = await get_channel_services(
            channel["id"]
        )

        if not services:
            await message.answer(
                "Is channel par koi service assigned nahi hai."
            )
            return

        channel_name = (
            channel.get("title")
            or channel.get("username")
            or str(channel["chat_id"])
        )

        output = (
            "ℹ️ CHANNEL SERVICE INFORMATION\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"Channel: {channel_name}\n"
        )

        for service in services:

            panel = await get_panel(
                service["panel_id"]
            )

            output += (
                "\n------------------\n"
                f"Panel: {panel['name'] if panel else 'Unavailable'}\n"
                f"Panel ID: {service['panel_id']}\n"
                f"Service ID: {service['service_id']}\n"
                f"Service: {service.get('service_name') or 'Unknown'}\n"
                f"Priority: {service.get('priority', 1)}\n"
                f"Status: {'Active' if service.get('active', True) else 'Inactive'}\n"
            )

        if len(output) > 4000:
            output = output[:3900] + "\n\nList shortened."

        await message.answer(output)

    except Exception as error:
        logger.exception("Service information failed")

        await message.answer(
            f"❌ Service info error: {str(error)[:300]}"
        )


@router.message(Command("checkservice"))
async def check_service(message: Message):

    if not await service_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 3:
        await message.answer(
            "Format:\n/checkservice PANEL_ID SERVICE_ID"
        )
        return

    try:
        panel_id = int(parts[1])
        service_id = int(parts[2])

        if panel_id <= 0 or service_id <= 0:
            raise ValueError

        panel = await get_panel(panel_id)

        if not panel or not panel_is_active(panel):
            await message.answer(
                "❌ Active panel nahi mila."
            )
            return

        selected = await find_panel_service(
            panel,
            service_id
        )

        if not selected:
            await message.answer(
                "❌ Yeh service ID panel par available nahi hai."
            )
            return

        await message.answer(
            "✅ SERVICE AVAILABLE\n\n"
            f"Panel: {panel['name']}\n"
            f"Service ID: {service_id}\n"
            f"Name: {selected.get('name', 'Unknown')}\n"
            f"Category: {selected.get('category', 'N/A')}\n"
            f"Rate: {selected.get('rate', 'N/A')}\n"
            f"Minimum: {selected.get('min', 'N/A')}\n"
            f"Maximum: {selected.get('max', 'N/A')}"
        )

    except ValueError:
        await message.answer(
            "❌ Panel ID aur Service ID positive numbers hone chahiye."
        )

    except Exception as error:
        logger.exception("Service check failed")

        await message.answer(
            f"❌ Service check error: {str(error)[:300]}"
        )


logger.info("Services router loaded successfully.")

