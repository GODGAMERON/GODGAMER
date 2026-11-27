
import logging

from aiogram import Router
from aiogram.types import Message

from database import (
    get_pool,
    get_channel,
    get_channel_services,
    get_panel,
)

from smm_api import SMMApi


router = Router()
logger = logging.getLogger(__name__)


def make_post_link(chat, message_id):
    """
    Public channel post link.
    Private channel links may not be accessible to SMM panels.
    """

    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"

    # Telegram private channel internal ID format
    chat_id = str(chat.id)

    if chat_id.startswith("-100"):
        internal_id = chat_id[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"

    return None


async def save_post_once(channel_id, message_id, post_url):
    """
    Insert post only once.
    Returns post database ID, or None if already processed.
    """

    pool = get_pool()

    async with pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            INSERT INTO channel_posts (
                channel_id,
                telegram_message_id,
                post_url,
                posted_at
            )
            VALUES ($1, $2, $3, NOW())
            ON CONFLICT (channel_id, telegram_message_id)
            DO NOTHING
            RETURNING id
            """,
            channel_id,
            message_id,
            post_url
        )

    return result["id"] if result else None


async def create_local_order(
    post_id,
    channel_id,
    channel_service_id,
    panel_id,
    service_id,
    quantity
):
    """
    Create local order record before sending the panel request.
    """

    pool = get_pool()

    async with pool.acquire() as connection:
        result = await connection.fetchrow(
            """
            INSERT INTO orders (
                channel_id,
                post_id,
                channel_service_id,
                panel_id,
                service_id,
                quantity,
                status,
                created_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, 'submitting', NOW(), NOW())
            ON CONFLICT (post_id, channel_service_id)
            WHERE channel_service_id IS NOT NULL
            DO NOTHING
            RETURNING id
            """,
            channel_id,
            post_id,
            channel_service_id,
            panel_id,
            service_id,
            quantity
        )

    return result["id"] if result else None


async def update_local_order(
    order_id,
    status,
    external_order_id=None,
    charge=None,
    error_message=None
):
    pool = get_pool()

    async with pool.acquire() as connection:
        await connection.execute(
            """
            UPDATE orders
            SET
                status = $2,
                external_order_id = COALESCE($3, external_order_id),
                charge = COALESCE($4, charge),
                error_message = $5,
                updated_at = NOW()
            WHERE id = $1
            """,
            order_id,
            status,
            external_order_id,
            charge,
            error_message
        )


async def place_order_for_service(
    post_id,
    channel,
    service,
    post_url,
    quantity
):
    service_id = int(service["service_id"])
    panel_id = int(service["panel_id"])

    if not post_url:
        logger.warning(
            "No usable post link for channel %s",
            channel["id"]
        )
        return

    panel = await get_panel(panel_id)

    if not panel or not panel.get("active", panel.get("is_active", False)):
        logger.error(
            "Assigned panel %s is unavailable",
            panel_id
        )
        return

    local_order_id = await create_local_order(
        post_id=post_id,
        channel_id=channel["id"],
        channel_service_id=service["id"],
        panel_id=panel_id,
        service_id=service_id,
        quantity=quantity
    )

    if not local_order_id:
        logger.info(
            "Order already exists for post %s and service %s",
            post_id,
            service_id
        )
        return

    try:
        api = SMMApi(
            api_url=panel["api_url"],
            api_key=panel["api_key"]
        )

        result = await api.add_order(
            service_id=service_id,
            link=post_url,
            quantity=quantity
        )

        external_id = result["order"]

        await update_local_order(
            order_id=local_order_id,
            status="pending",
            external_order_id=external_id,
            error_message=None
        )

        logger.info(
            "Order created: local=%s external=%s quantity=%s",
            local_order_id,
            external_id,
            quantity
        )

    except Exception as error:
        logger.exception(
            "Panel order failed for local order %s",
            local_order_id
        )

        await update_local_order(
            order_id=local_order_id,
            status="failed",
            error_message=str(error)[:1000]
        )


@router.channel_post()
async def handle_new_channel_post(message: Message):
    """
    Automatically process every new channel post.
    """

    chat = message.chat

    if chat.type != "channel":
        return

    try:
        channel = await get_channel(chat.id)

        if not channel:
            logger.info(
                "Unregistered channel post received: %s",
                chat.id
            )
            return

        if not channel.get("is_active"):
            return

        if not channel.get("automation_enabled"):
            return

        services = await get_channel_services(
            channel["id"],
            active_only=True
        )

        if not services:
            logger.warning(
                "No active services assigned to channel %s",
                chat.id
            )
            return

        post_url = make_post_link(
            chat,
            message.message_id
        )

        post_id = await save_post_once(
            channel_id=channel["id"],
            message_id=message.message_id,
            post_url=post_url
        )

        if not post_id:
            logger.info(
                "Duplicate post ignored: channel=%s message=%s",
                chat.id,
                message.message_id
            )
            return

        logger.info(
            "New post detected: channel=%s message=%s services=%s",
            chat.id,
            message.message_id,
            len(services)
        )

        # Each assigned service gets its own independent order.
        # One failed service does not stop the remaining services.
        for service in services:
            try:
                service_quantity = int(service.get("quantity") or 0)
                if service_quantity <= 0:
                    logger.warning(
                        "Skipping service %s: quantity is not configured",
                        service.get("service_id")
                    )
                    continue
                await place_order_for_service(
                    post_id=post_id,
                    channel=channel,
                    service=service,
                    post_url=post_url,
                    quantity=service_quantity
                )

            except Exception:
                logger.exception(
                    "Service processing failed: channel=%s service=%s",
                    chat.id,
                    service.get("service_id")
                )

    except Exception:
        logger.exception(
            "New channel post processing failed for chat %s",
            chat.id
        )
