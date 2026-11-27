
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


def is_panel_active(panel):
    """Support both old and current database field names."""

    if not panel:
        return False

    return bool(
        panel.get("active", panel.get("is_active", False))
    )


def make_post_link(chat, message_id):
    """Create a Telegram post link for public or private channels."""

    if chat.username:
        return f"https://t.me/{chat.username}/{message_id}"

    chat_id = str(chat.id)

    if chat_id.startswith("-100"):
        internal_id = chat_id[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"

    return None


async def save_post_once(channel_id, message_id, post_url):
    """
    Save a Telegram post only once.

    Returns:
        Database post ID if inserted.
        None if the post was already processed.
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
    Create a local order before contacting the SMM panel.

    This prevents duplicate orders for the same post and service.
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
            VALUES (
                $1, $2, $3, $4, $5, $6,
                'submitting', NOW(), NOW()
            )
            ON CONFLICT (post_id, channel_service_id)
            WHERE channel_service_id IS NOT NULL
            DO NOTHING
            RETURNING id
            """,
            channel_id,
            post_id,
            channel_service_id,
            panel_id,
            str(service_id),
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
    """Update local order status and panel response."""

    pool = get_pool()

    async with pool.acquire() as connection:
        await connection.execute(
            """
            UPDATE orders
            SET
                status = $2,
                external_order_id = COALESCE(
                    $3,
                    external_order_id
                ),
                charge = COALESCE($4, charge),
                error_message = $5,
                updated_at = NOW()
            WHERE id = $1
            """,
            order_id,
            status,
            str(external_order_id) if external_order_id is not None else None,
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
    """Place one independent order for one assigned service."""

    service_id = int(service["service_id"])
    panel_id = int(service["panel_id"])
    channel_service_id = int(service["id"])

    local_order_id = await create_local_order(
        post_id=post_id,
        channel_id=channel["id"],
        channel_service_id=channel_service_id,
        panel_id=panel_id,
        service_id=service_id,
        quantity=quantity
    )

    if not local_order_id:
        logger.info(
            "Duplicate order ignored: post=%s service=%s",
            post_id,
            service_id
        )
        return

    try:
        if not post_url:
            raise ValueError("Telegram post link is unavailable.")

        panel = await get_panel(panel_id)

        if not panel or not is_panel_active(panel):
            raise ValueError(
                f"Panel {panel_id} is unavailable or inactive."
            )

        api_url = panel.get("api_url")
        api_key = panel.get("api_key")

        if not api_url or not api_key:
            raise ValueError(
                f"Panel {panel_id} API configuration is incomplete."
            )

        api = SMMApi(
            api_url=api_url,
            api_key=api_key
        )

        result = await api.add_order(
            service_id=service_id,
            link=post_url,
            quantity=quantity
        )

        external_id = result.get("order")

        if not external_id:
            raise ValueError(
                "Panel did not return an external order ID."
            )

        await update_local_order(
            order_id=local_order_id,
            status="pending",
            external_order_id=external_id,
            error_message=None
        )

        logger.info(
            "SMM order placed successfully: "
            "local=%s external=%s channel=%s "
            "service=%s quantity=%s",
            local_order_id,
            external_id,
            channel["id"],
            service_id,
            quantity
        )

    except Exception as error:
        logger.exception(
            "Order placement failed: local_order=%s service=%s",
            local_order_id,
            service_id
        )

        try:
            await update_local_order(
                order_id=local_order_id,
                status="failed",
                error_message=str(error)[:1000]
            )
        except Exception:
            logger.exception(
                "Could not update failed order %s",
                local_order_id
            )


@router.channel_post()
async def handle_new_channel_post(message: Message):
    """
    Automatically place independent SMM orders
    for every new post in a registered channel.
    """

    chat = message.chat

    if chat.type != "channel":
        return

    try:
        channel = await get_channel(chat.id)

        if not channel:
            logger.info(
                "Unregistered channel post: %s",
                chat.id
            )
            return

        if not channel.get("is_active"):
            logger.info(
                "Inactive channel ignored: %s",
                chat.id
            )
            return

        if not channel.get("automation_enabled"):
            logger.info(
                "Automation disabled for channel: %s",
                chat.id
            )
            return

        quantity = int(channel.get("quantity") or 0)

        if quantity <= 0:
            logger.warning(
                "Invalid quantity for channel %s",
                chat.id
            )
            return

        post_url = make_post_link(
            chat,
            message.message_id
        )

        if not post_url:
            logger.error(
                "Could not create post link: channel=%s message=%s",
                chat.id,
                message.message_id
            )
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
            "New post detected: channel=%s message=%s "
            "services=%s quantity=%s",
            chat.id,
            message.message_id,
            len(services),
            quantity
        )

        # Each service is processed independently.
        # A failure in one service will not stop other services.

        for service in services:
            try:
                await place_order_for_service(
                    post_id=post_id,
                    channel=channel,
                    service=service,
                    post_url=post_url,
                    quantity=quantity
                )

            except Exception:
                logger.exception(
                    "Service processing error: "
                    "channel=%s service=%s",
                    chat.id,
                    service.get("service_id")
                )

    except Exception:
        logger.exception(
            "Channel post processing failed: chat=%s message=%s",
            chat.id,
            message.message_id
        )


logger.info("Order engine loaded successfully.")
