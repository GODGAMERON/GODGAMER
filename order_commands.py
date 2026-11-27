
import logging
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import (
    get_order,
    get_orders,
    update_order_status,
    get_panel,
)

from admin_permissions import has_permission
from smm_api import SMMApi


router = Router()
logger = logging.getLogger(__name__)


# ==========================================
# ORDER PERMISSION
# ==========================================

async def order_permission(message: Message) -> bool:

    if not message.from_user:
        return False

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


# ==========================================
# STATUS MAPPING
# ==========================================

STATUS_MAP = {
    "pending": "pending",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "processing": "in_progress",
    "completed": "completed",
    "partial": "partial",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "failed": "failed",
}


def normalize_status(status):

    return STATUS_MAP.get(
        str(status or "").strip().lower()
    )


# ==========================================
# RECENT ORDERS
# ==========================================

@router.message(Command("orders"))
async def orders_command(message: Message):

    if not await order_permission(message):
        return

    try:
        orders = await get_orders(limit=20)

        if not orders:
            await message.answer(
                "📦 Abhi database mein koi order nahi hai."
            )
            return

        output = (
            "📦 <b>RECENT ORDERS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

        for order in orders:

            output += (
                f"\n<b>Order ID:</b> {order['id']}\n"
                f"<b>Service:</b> {escape(str(order['service_id']))}\n"
                f"<b>Quantity:</b> {order['quantity']}\n"
                f"<b>Status:</b> {escape(str(order['status']))}\n"
                f"<b>External ID:</b> "
                f"{escape(str(order.get('external_order_id') or 'N/A'))}\n"
                "━━━━━━━━━━━━━━━━━━\n"
            )

        await message.answer(output[:4000])

    except Exception:
        logger.exception("Recent orders command failed.")

        await message.answer(
            "❌ Orders load nahi ho paaye. Logs check karein."
        )


# ==========================================
# PENDING ORDERS
# ==========================================

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
            await message.answer(
                "✅ Koi pending order nahi hai."
            )
            return

        output = (
            "⏳ <b>PENDING ORDERS</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

        for order in orders:

            output += (
                f"\n<b>Local ID:</b> {order['id']}\n"
                f"<b>External ID:</b> "
                f"{escape(str(order.get('external_order_id') or 'N/A'))}\n"
                f"<b>Service ID:</b> {escape(str(order['service_id']))}\n"
                f"<b>Quantity:</b> {order['quantity']}\n"
                "━━━━━━━━━━━━━━━━━━\n"
            )

        await message.answer(output[:4000])

    except Exception:
        logger.exception("Pending orders command failed.")

        await message.answer(
            "❌ Pending orders load nahi ho paaye."
        )


# ==========================================
# ORDER INFORMATION
# ==========================================

@router.message(Command("orderinfo"))
async def order_info_command(message: Message):

    if not await order_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/orderinfo ORDER_ID"
        )
        return

    try:
        order_id = int(parts[1])

        if order_id <= 0:
            await message.answer("❌ Invalid Order ID.")
            return

        order = await get_order(order_id)

        if not order:
            await message.answer(
                "❌ Order nahi mila."
            )
            return

        output = (
            "ℹ️ <b>ORDER INFORMATION</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Local ID:</b> {order['id']}\n"
            f"<b>External ID:</b> "
            f"{escape(str(order.get('external_order_id') or 'N/A'))}\n"
            f"<b>Channel ID:</b> {order['channel_id']}\n"
            f"<b>Service ID:</b> {escape(str(order['service_id']))}\n"
            f"<b>Panel ID:</b> {order.get('panel_id') or 'N/A'}\n"
            f"<b>Quantity:</b> {order['quantity']}\n"
            f"<b>Status:</b> {escape(str(order['status']))}\n"
            f"<b>Charge:</b> {escape(str(order.get('charge') or 'N/A'))}\n"
            f"<b>Error:</b> "
            f"{escape(str(order.get('error_message') or 'None'))}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

        await message.answer(output[:4000])

    except ValueError:
        await message.answer(
            "❌ Order ID number mein bhejein."
        )

    except Exception:
        logger.exception("Order information command failed.")

        await message.answer(
            "❌ Order information load nahi ho payi."
        )


# ==========================================
# CHECK ORDER STATUS
# ==========================================

@router.message(Command("checkorder"))
async def check_order_command(message: Message):

    if not await order_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/checkorder ORDER_ID"
        )
        return

    try:
        order_id = int(parts[1])

        if order_id <= 0:
            await message.answer("❌ Invalid Order ID.")
            return

        order = await get_order(order_id)

        if not order:
            await message.answer(
                "❌ Order nahi mila."
            )
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
            api_url=panel["api_url"],
            api_key=panel["api_key"]
        )

        result = await api.get_order_status(
            str(external_id)
        )

        raw_status = str(
            result.get("status", "")
        ).strip().lower()

        new_status = normalize_status(raw_status)

        if new_status:

            await update_order_status(
                order_id=order_id,
                status=new_status
            )

        else:
            logger.warning(
                "Unknown panel status for order %s: %s",
                order_id,
                raw_status
            )

        database_status = new_status or order["status"]

        await message.answer(
            "🔄 <b>ORDER STATUS CHECK</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Local Order:</b> {order_id}\n"
            f"<b>Panel Order:</b> {escape(str(external_id))}\n"
            f"<b>Panel Status:</b> {escape(raw_status or 'Unknown')}\n"
            f"<b>Database Status:</b> {escape(str(database_status))}\n"
            "━━━━━━━━━━━━━━━━━━"
        )

    except ValueError:
        await message.answer(
            "❌ Order ID number mein bhejein."
        )

    except Exception:
        logger.exception("Order status check failed.")

        await message.answer(
            "❌ Order status check nahi ho paya. Logs check karein."
        )


# ==========================================
# CANCEL ORDER
# ==========================================

@router.message(Command("cancelorder"))
async def cancel_order_command(message: Message):

    if not await order_permission(message):
        return

    parts = (message.text or "").split()

    if len(parts) != 2:
        await message.answer(
            "Format:\n/cancelorder ORDER_ID"
        )
        return

    try:
        order_id = int(parts[1])

        if order_id <= 0:
            await message.answer("❌ Invalid Order ID.")
            return

        order = await get_order(order_id)

        if not order:
            await message.answer(
                "❌ Order nahi mila."
            )
            return

        external_id = order.get("external_order_id")

        if not external_id:
            await message.answer(
                "❌ Panel order ID available nahi hai."
            )
            return

        if order["status"] in (
            "completed",
            "cancelled",
            "failed"
        ):
            await message.answer(
                f"⚠️ Is order ka status {order['status']} hai.\n"
                "Cancellation request nahi bheji gayi."
            )
            return

        panel = await get_panel(order["panel_id"])

        if not panel or not panel.get("active"):
            await message.answer(
                "❌ Assigned panel unavailable hai."
            )
            return

        api = SMMApi(
            api_url=panel["api_url"],
            api_key=panel["api_key"]
        )

        result = await api.cancel_order(
            str(external_id)
        )

        await message.answer(
            "📨 <b>CANCELLATION REQUEST SENT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Local Order:</b> {order_id}\n"
            f"<b>Panel Order:</b> {escape(str(external_id))}\n"
            f"<b>Panel Response:</b>\n"
            f"<code>{escape(str(result)[:1500])}</code>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Note: Cancellation tabhi confirm hogi "
            "jab panel status cancelled return karega."
        )

    except ValueError:
        await message.answer(
            "❌ Order ID number mein bhejein."
        )

    except Exception:
        logger.exception("Order cancellation failed.")

        await message.answer(
            "❌ Cancellation request fail ho gayi."
        )

