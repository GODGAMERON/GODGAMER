
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_order, get_orders, update_order_status, get_panel
from admin_permissions import has_permission
from smm_api import SMMApi

router = Router()


async def order_permission(message: Message) -> bool:
    allowed = await has_permission(
        message.from_user.id,
        "order_management"
    )

    if not allowed:
        await message.answer(
            "❌ Aapko Order Management permission nahi hai."
        )
        return False

    return True


@router.message(Command("orders"))
async def orders_command(message: Message):
    if not await order_permission(message):
        return

    try:
        orders = await get_orders(limit=20)

        if not orders:
            await message.answer("Abhi koi order nahi hai.")
            return

        output = "📦 RECENT ORDERS\n━━━━━━━━━━━━━━━━━━\n"

        for order in orders:
            output += (
                f"\nOrder ID: {order['id']}\n"
                f"Service ID: {order['service_id']}\n"
                f"Quantity: {order['quantity']}\n"
                f"Status: {order['status']}\n"
                f"External ID: {order.get('external_order_id') or 'N/A'}\n"
                "------------------\n"
            )

        await message.answer(output[:4000])

    except Exception as error:
        await message.answer(
            f"❌ Orders error: {str(error)[:300]}"
        )


@router.message(Command("pendingorders"))
async def pending_orders_command(message: Message):
    if not await order_permission(message):
        return

    try:
        orders = await get_orders(
            status="pending",
            limit=50
        )

        if not orders:
            await message.answer("✅ Koi pending order nahi hai.")
            return

        output = "⏳ PENDING ORDERS\n━━━━━━━━━━━━━━━━━━\n"

        for order in orders:
            output += (
                f"\nLocal ID: {order['id']}\n"
                f"External ID: {order.get('external_order_id') or 'N/A'}\n"
                f"Service ID: {order['service_id']}\n"
                f"Quantity: {order['quantity']}\n"
                "------------------\n"
            )

        await message.answer(output[:4000])

    except Exception as error:
        await message.answer(
            f"❌ Pending orders error: {str(error)[:300]}"
        )


@router.message(Command("orderinfo"))
async def order_info_command(message: Message):
    if not await order_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer("Format:\n/orderinfo ORDER_ID")
        return

    try:
        order_id = int(parts[1])
        order = await get_order(order_id)

        if not order:
            await message.answer("❌ Order nahi mila.")
            return

        await message.answer(
            "ℹ️ ORDER INFORMATION\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"Local ID: {order['id']}\n"
            f"External ID: {order.get('external_order_id') or 'N/A'}\n"
            f"Channel ID: {order['channel_id']}\n"
            f"Service ID: {order['service_id']}\n"
            f"Panel ID: {order['panel_id']}\n"
            f"Quantity: {order['quantity']}\n"
            f"Status: {order['status']}\n"
            f"Charge: {order.get('charge') or 'N/A'}\n"
            f"Error: {order.get('error_message') or 'None'}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

    except ValueError:
        await message.answer("❌ Order ID number mein bhejein.")

    except Exception as error:
        await message.answer(
            f"❌ Order info error: {str(error)[:300]}"
        )


@router.message(Command("checkorder"))
async def check_order_command(message: Message):
    if not await order_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer("Format:\n/checkorder ORDER_ID")
        return

    try:
        order_id = int(parts[1])
        order = await get_order(order_id)

        if not order:
            await message.answer("❌ Order nahi mila.")
            return

        external_id = order.get("external_order_id")

        if not external_id:
            await message.answer(
                "❌ Is order ka external panel ID available nahi hai.\n"
                f"Current status: {order['status']}"
            )
            return

        panel = await get_panel(order["panel_id"])

        if not panel or not panel.get("active"):
            await message.answer(
                "❌ Assigned panel inactive ya unavailable hai."
            )
            return

        api = SMMApi(
            panel["api_url"],
            panel["api_key"]
        )

        result = await api.get_order_status(str(external_id))

        raw_status = str(
            result.get("status", "")
        ).strip().lower()

        status_map = {
            "pending": "pending",
            "in progress": "in_progress",
            "processing": "in_progress",
            "completed": "completed",
            "partial": "partial",
            "canceled": "cancelled",
            "cancelled": "cancelled",
            "failed": "failed",
        }

        new_status = status_map.get(raw_status)

        if new_status:
            await update_order_status(
                order_id,
                new_status
            )

        await message.answer(
            "🔄 ORDER STATUS CHECK\n\n"
            f"Local Order: {order_id}\n"
            f"Panel Order: {external_id}\n"
            f"Panel Status: {raw_status or 'Unknown'}\n"
            f"Database Status: {new_status or order['status']}"
        )

    except ValueError:
        await message.answer("❌ Order ID number mein bhejein.")

    except Exception as error:
        await message.answer(
            f"❌ Order check failed: {str(error)[:300]}"
        )


@router.message(Command("cancelorder"))
async def cancel_order_command(message: Message):
    if not await order_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer("Format:\n/cancelorder ORDER_ID")
        return

    try:
        order_id = int(parts[1])
        order = await get_order(order_id)

        if not order:
            await message.answer("❌ Order nahi mila.")
            return

        external_id = order.get("external_order_id")

        if not external_id:
            await message.answer(
                "❌ Panel order ID available nahi hai."
            )
            return

        if order["status"] in ("completed", "cancelled", "failed"):
            await message.answer(
                f"⚠️ Is order ka status {order['status']} hai. "
                "Cancellation request nahi bheji gayi."
            )
            return

        panel = await get_panel(order["panel_id"])

        if not panel or not panel.get("active"):
            await message.answer("❌ Assigned panel unavailable hai.")
            return

        api = SMMApi(
            panel["api_url"],
            panel["api_key"]
        )

        result = await api.cancel_order(str(external_id))

        await message.answer(
            "📨 Cancellation request panel ko bhej di gayi.\n\n"
            f"Local Order: {order_id}\n"
            f"Panel Order: {external_id}\n"
            f"Panel Response: {str(result)[:1000]}\n\n"
            "Note: Cancellation tabhi confirm hogi jab panel "
            "status cancelled return kare."
        )

    except ValueError:
        await message.answer("❌ Order ID number mein bhejein.")

    except Exception as error:
        await message.answer(
            f"❌ Cancellation failed: {str(error)[:300]}"
        )
