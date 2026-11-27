
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from database import (
    add_panel,
    get_panel,
    get_panel_by_name,
    get_all_panels,
    remove_panel,
    update_panel_balance,
)

from admin_permissions import has_permission

from smm_api import (
    check_panel_connection,
    get_panel_services,
)


router = Router()
logger = logging.getLogger(__name__)


class AddPanelState(StatesGroup):
    name = State()
    api_url = State()
    api_key = State()


def is_panel_active(panel):
    """Support both active and is_active database fields."""

    if not panel:
        return False

    return bool(
        panel.get("active", panel.get("is_active", False))
    )


async def panel_permission(message: Message) -> bool:
    """Check panel management permission safely."""

    if not message.from_user:
        return False

    allowed = await has_permission(
        message.from_user.id,
        "panel_management"
    )

    if not allowed:
        await message.answer(
            "❌ Aapko Panel Management permission nahi hai."
        )
        return False

    return True


@router.message(Command("ADDNEW"))
async def add_new_panel(message: Message, state: FSMContext):
    if not await panel_permission(message):
        return

    if message.chat.type != "private":
        await message.answer(
            "⚠️ Panel setup sirf bot ke private chat mein karein."
        )
        return

    await state.clear()
    await state.set_state(AddPanelState.name)

    await message.answer(
        "➕ NEW SMM PANEL\n\n"
        "Sabse pehle panel ka naam bhejiye.\n\n"
        "Example: PanelOne\n\n"
        "Cancel karne ke liye /cancel bhejein."
    )


@router.message(Command("cancel"))
async def cancel_panel_setup(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state:
        await state.clear()
        await message.answer(
            "❌ Panel setup cancel kar diya gaya."
        )
    else:
        await message.answer(
            "Koi active setup nahi hai."
        )


@router.message(AddPanelState.name)
async def receive_panel_name(message: Message, state: FSMContext):
    if not await panel_permission(message):
        await state.clear()
        return

    name = (message.text or "").strip()

    if not name or len(name) > 80:
        await message.answer(
            "❌ Panel name 1 se 80 characters ke beech hona chahiye."
        )
        return

    try:
        existing = await get_panel_by_name(name)

        if existing:
            await message.answer(
                "❌ Is naam ka panel pehle se database mein hai. "
                "Dusra naam bhejein."
            )
            return

        await state.update_data(panel_name=name)
        await state.set_state(AddPanelState.api_url)

        await message.answer(
            "Ab panel ka API URL bhejein.\n\n"
            "Example:\n"
            "https://example.com/api/v2"
        )

    except Exception as error:
        logger.exception("Panel name validation failed")

        await message.answer(
            f"❌ Error: {str(error)[:300]}"
        )


@router.message(AddPanelState.api_url)
async def receive_panel_url(message: Message, state: FSMContext):
    if not await panel_permission(message):
        await state.clear()
        return

    api_url = (message.text or "").strip()

    if not api_url.startswith(("http://", "https://")):
        await message.answer(
            "❌ Valid HTTP/HTTPS API URL bhejein."
        )
        return

    await state.update_data(api_url=api_url)
    await state.set_state(AddPanelState.api_key)

    await message.answer(
        "Ab panel ki API KEY bhejein.\n\n"
        "⚠️ API key kisi group mein share na karein. "
        "Is bot ke private chat mein hi bhejein."
    )


@router.message(AddPanelState.api_key)
async def receive_panel_key(message: Message, state: FSMContext):
    if not await panel_permission(message):
        await state.clear()
        return

    if message.chat.type != "private":
        await state.clear()
        await message.answer(
            "❌ Security ke liye panel API key sirf private chat mein bhejein."
        )
        return

    api_key = (message.text or "").strip()

    if not api_key:
        await message.answer(
            "❌ API key empty nahi ho sakti."
        )
        return

    # API key ko chat history mein rakhne se bachayein.
    try:
        await message.delete()
    except Exception:
        logger.warning(
            "Could not delete API key message. Check bot permissions."
        )

    data = await state.get_data()

    panel_name = data.get("panel_name")
    api_url = data.get("api_url")

    if not panel_name or not api_url:
        await state.clear()
        await message.answer(
            "❌ Panel setup data missing hai. /ADDNEW se dobara shuru karein."
        )
        return

    status_message = await message.answer(
        "⏳ Panel API connection test ho raha hai..."
    )

    try:
        connection = await check_panel_connection(
            api_url,
            api_key
        )

        if not connection or not connection.get("connected"):
            raise ValueError(
                "Panel connection verify nahi hua."
            )

        existing = await get_panel_by_name(panel_name)

        if existing:
            raise ValueError(
                "Is naam ka panel pehle se registered hai."
            )

        await add_panel(
            name=panel_name,
            api_url=api_url,
            api_key=api_key,
            added_by=message.from_user.id
        )

        saved_panel = await get_panel_by_name(panel_name)

        await state.clear()

        await status_message.edit_text(
            "✅ SMM PANEL SUCCESSFULLY ADDED!\n\n"
            f"Panel: {panel_name}\n"
            f"Panel ID: {saved_panel['id'] if saved_panel else 'Saved'}\n"
            f"Balance: {connection.get('balance')}\n"
            f"Currency: {connection.get('currency')}\n\n"
            "Panel ab service assignment ke liye available hai."
        )

    except Exception as error:
        await state.clear()

        logger.exception(
            "Panel registration failed"
        )

        await status_message.edit_text(
            "❌ Panel add nahi ho paya.\n\n"
            f"Reason: {str(error)[:400]}\n\n"
            "API URL aur API KEY verify karein."
        )


@router.message(Command("Allsmmpanel"))
async def all_smm_panels(message: Message):
    if not await panel_permission(message):
        return

    try:
        panels = await get_all_panels(active_only=False)

        if not panels:
            await message.answer(
                "Abhi koi SMM panel add nahi hai."
            )
            return

        output = (
            "📋 ALL SMM PANELS\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

        for panel in panels:
            status = (
                "🟢 Active"
                if is_panel_active(panel)
                else "🔴 Inactive"
            )

            output += (
                f"\nID: {panel['id']}\n"
                f"Name: {panel['name']}\n"
                f"Status: {status}\n"
                "━━━━━━━━━━━━━━━━━━\n"
            )

            if len(output) >= 3500:
                await message.answer(output)
                output = ""

        if output:
            await message.answer(output)

    except Exception as error:
        logger.exception("Panel list failed")

        await message.answer(
            f"❌ Panel list error: {str(error)[:300]}"
        )


@router.message(Command("Removesmm"))
async def remove_smm_panel(message: Message):
    if not await panel_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/Removesmm PANEL_ID\n\n"
            "Example:\n/Removesmm 1"
        )
        return

    try:
        panel_id = int(parts[1])

        panel = await get_panel(panel_id)

        if not panel:
            await message.answer(
                "❌ Panel nahi mila."
            )
            return

        if not is_panel_active(panel):
            await message.answer(
                "⚠️ Panel pehle se inactive hai."
            )
            return

        await remove_panel(panel_id)

        await message.answer(
            "✅ Panel deactivate kar diya gaya.\n\n"
            f"Panel: {panel['name']}\n"
            f"ID: {panel_id}\n\n"
            "Purane orders aur history database mein rahenge."
        )

    except ValueError:
        await message.answer(
            "❌ Panel ID number mein bhejein."
        )

    except Exception as error:
        logger.exception("Panel removal failed")

        await message.answer(
            f"❌ Panel remove error: {str(error)[:300]}"
        )


@router.message(Command("panelinfo"))
async def panel_info(message: Message):
    if not await panel_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/panelinfo PANEL_ID"
        )
        return

    try:
        panel_id = int(parts[1])
        panel = await get_panel(panel_id)

        if not panel:
            await message.answer(
                "❌ Panel nahi mila."
            )
            return

        await message.answer(
            "ℹ️ PANEL INFORMATION\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"ID: {panel['id']}\n"
            f"Name: {panel['name']}\n"
            f"API URL: {panel['api_url']}\n"
            f"Status: {'Active' if is_panel_active(panel) else 'Inactive'}\n"
            f"Last Balance: {panel.get('last_balance')}\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "API KEY: Hidden"
        )

    except ValueError:
        await message.answer(
            "❌ Panel ID number mein bhejein."
        )

    except Exception as error:
        logger.exception("Panel information failed")

        await message.answer(
            f"❌ Panel info error: {str(error)[:300]}"
        )


@router.message(Command("checkbalance"))
async def check_balance(message: Message):
    if not await panel_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/checkbalance PANEL_ID"
        )
        return

    try:
        panel_id = int(parts[1])
        panel = await get_panel(panel_id)

        if not panel:
            await message.answer(
                "❌ Panel nahi mila."
            )
            return

        if not is_panel_active(panel):
            await message.answer(
                "❌ Yeh panel inactive hai."
            )
            return

        result = await check_panel_connection(
            panel["api_url"],
            panel["api_key"]
        )

        balance = result.get("balance")
        currency = result.get("currency")

        await update_panel_balance(
            panel_id,
            balance
        )

        await message.answer(
            "💰 PANEL BALANCE\n\n"
            f"Panel: {panel['name']}\n"
            f"Balance: {balance}\n"
            f"Currency: {currency}"
        )

    except ValueError:
        await message.answer(
            "❌ Panel ID number mein bhejein."
        )

    except Exception as error:
        logger.exception("Panel balance check failed")

        await message.answer(
            f"❌ Balance check failed: {str(error)[:300]}"
        )


@router.message(Command("checkservices"))
async def check_services(message: Message):
    if not await panel_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/checkservices PANEL_ID"
        )
        return

    try:
        panel_id = int(parts[1])
        panel = await get_panel(panel_id)

        if not panel:
            await message.answer(
                "❌ Panel nahi mila."
            )
            return

        if not is_panel_active(panel):
            await message.answer(
                "❌ Yeh panel inactive hai."
            )
            return

        services = await get_panel_services(
            panel["api_url"],
            panel["api_key"]
        )

        if not services:
            await message.answer(
                "Is panel par koi service nahi mili."
            )
            return

        output = (
            f"📦 SERVICES: {panel['name']}\n"
            f"Total Services: {len(services)}\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

        for service in services[:30]:
            output += (
                f"\nID: {service.get('service')}\n"
                f"Name: {service.get('name', 'Unknown')}\n"
                f"Category: {service.get('category', 'N/A')}\n"
                f"Rate: {service.get('rate', 'N/A')}\n"
                f"Min: {service.get('min', 'N/A')}\n"
                f"Max: {service.get('max', 'N/A')}\n"
                "------------------\n"
            )

            if len(output) >= 3500:
                await message.answer(output)
                output = ""

        if len(services) > 30:
            output += (
                f"\nAur {len(services) - 30} services hain."
            )

        if output:
            await message.answer(output)

    except ValueError:
        await message.answer(
            "❌ Panel ID number mein bhejein."
        )

    except Exception as error:
        logger.exception("Panel services check failed")

        await message.answer(
            f"❌ Services check failed: {str(error)[:300]}"
        )


logger.info("Panel management router loaded successfully.")
