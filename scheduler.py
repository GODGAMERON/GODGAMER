
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import (
    get_pool,
    update_order_status,
    get_panel,
)

from smm_api import SMMApi

from config import ORDER_STATUS_CHECK_SECONDS


logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(
    timezone="Asia/Kolkata"
)


STATUS_MAP = {
    "pending": "pending",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "inprogress": "in_progress",
    "processing": "in_progress",
    "completed": "completed",
    "complete": "completed",
    "partial": "partial",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "failed": "failed",
    "error": "failed",
}


def panel_is_active(panel):
    if not panel:
        return False

    return bool(
        panel.get("is_active", panel.get("active", False))
    )


async def check_pending_orders():

    pool = get_pool()

    if pool is None:
        logger.error(
            "Database pool is not initialized."
        )
        return

    try:
        async with pool.acquire() as connection:

            orders = await connection.fetch(
                """
                SELECT
                    id,
                    external_order_id,
                    status,
                    panel_id
                FROM orders
                WHERE
                    external_order_id IS NOT NULL
                    AND LOWER(status) IN (
                        'pending',
                        'in_progress',
                        'processing',
                        'partial',
                        'submitting'
                    )
                ORDER BY created_at ASC
                LIMIT 200
                """
            )

        if not orders:
            logger.debug(
                "No pending orders to check."
            )
            return

        logger.info(
            "Checking %s pending orders.",
            len(orders)
        )

        for order in orders:

            try:
                order_id = order["id"]
                external_order_id = order["external_order_id"]
                panel_id = order["panel_id"]

                if not external_order_id or not panel_id:
                    continue

                panel = await get_panel(panel_id)

                if not panel or not panel_is_active(panel):
                    logger.warning(
                        "Panel unavailable for order %s",
                        order_id
                    )
                    continue

                api = SMMApi(
                    api_url=panel["api_url"],
                    api_key=panel["api_key"]
                )

                result = await api.get_order_status(
                    str(external_order_id)
                )

                if not isinstance(result, dict):
                    logger.warning(
                        "Invalid status response for order %s",
                        order_id
                    )
                    continue

                raw_status = str(
                    result.get("status", "")
                ).strip().lower()

                new_status = STATUS_MAP.get(raw_status)

                if not new_status:
                    logger.warning(
                        "Unknown status '%s' for order %s",
                        raw_status,
                        order_id
                    )
                    continue

                old_status = str(
                    order["status"]
                ).strip().lower()

                charge = result.get("charge")

                try:
                    if charge is not None:
                        charge = float(charge)
                except (TypeError, ValueError):
                    charge = None

                if new_status != old_status or charge is not None:

                    await update_order_status(
                        order_id=order_id,
                        status=new_status,
                        charge=charge,
                        error_message=None
                    )

                    logger.info(
                        "Order %s updated: %s -> %s",
                        order_id,
                        old_status,
                        new_status
                    )

            except Exception:
                logger.exception(
                    "Could not check order %s",
                    order.get("id")
                )

    except Exception:
        logger.exception(
            "Pending order checker failed."
        )


# --------------------------------------------------
# START SCHEDULER
# --------------------------------------------------

def start_scheduler():

    if scheduler.running:
        logger.info(
            "Scheduler already running."
        )
        return

    interval = max(
        15,
        int(ORDER_STATUS_CHECK_SECONDS)
    )

    scheduler.add_job(
        check_pending_orders,
        trigger="interval",
        seconds=interval,
        id="pending_order_checker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30
    )

    scheduler.start()

    logger.info(
        "Order status scheduler started. "
        "Interval: %s seconds.",
        interval
    )


# --------------------------------------------------
# STOP SCHEDULER
# --------------------------------------------------

def stop_scheduler():

    if scheduler.running:
        scheduler.shutdown(wait=False)

        logger.info(
            "Order status scheduler stopped."
        )
