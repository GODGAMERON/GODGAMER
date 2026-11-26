
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    get_pool,
    get_order,
    update_order_status,
    get_panel,
)

from smm_api import SMMApi
from config import ORDER_STATUS_CHECK_SECONDS


logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

STATUS_MAP = {
    "pending": "pending",
    "in progress": "in_progress",
    "processing": "in_progress",
    "completed": "completed",
    "partial": "partial",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "failed": "failed",
}


async def check_pending_orders():
    """
    Background task:
    Fetch pending orders and synchronize their status
    with their assigned SMM panel.
    """

    pool = get_pool()

    if pool is None:
        logger.error("Database pool is not initialized.")
        return

    try:
        async with pool.acquire() as connection:
            orders = await connection.fetch(
                """
                SELECT
                    o.id,
                    o.external_order_id,
                    o.status,
                    o.panel_id
                FROM orders o
                WHERE
                    o.external_order_id IS NOT NULL
                    AND LOWER(o.status) IN (
                        'pending',
                        'in_progress',
                        'processing',
                        'partial'
                    )
                ORDER BY o.created_at ASC
                LIMIT 200
                """
            )

        for order in orders:
            try:
                panel = await get_panel(order["panel_id"])

                if not panel or not panel.get("active"):
                    logger.warning(
                        "Panel unavailable for order %s",
                        order["id"]
                    )
                    continue

                api = SMMApi(
                    api_url=panel["api_url"],
                    api_key=panel["api_key"]
                )

                result = await api.get_order_status(
                    str(order["external_order_id"])
                )

                raw_status = str(
                    result.get("status", "")
                ).strip().lower()

                new_status = STATUS_MAP.get(raw_status)

                if not new_status:
                    logger.warning(
                        "Unknown status '%s' for order %s",
                        raw_status,
                        order["id"]
                    )
                    continue

                if new_status != order["status"]:
                    await update_order_status(
                        order_id=order["id"],
                        status=new_status
                    )

                    logger.info(
                        "Order %s updated: %s -> %s",
                        order["id"],
                        order["status"],
                        new_status
                    )

            except Exception:
                logger.exception(
                    "Could not check order %s",
                    order["id"]
                )

    except Exception:
        logger.exception("Pending order checker failed")


def start_scheduler():
    if scheduler.running:
        logger.info("Scheduler already running.")
        return

    interval = max(15, int(ORDER_STATUS_CHECK_SECONDS))

    scheduler.add_job(
        check_pending_orders,
        trigger="interval",
        seconds=interval,
        id="pending_order_checker",
        replace_existing=True,
        max_instances=1,
        coalesce=True
    )

    scheduler.start()

    logger.info(
        "Order status scheduler started. Interval: %s seconds",
        interval
    )


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Order status scheduler stopped.")
