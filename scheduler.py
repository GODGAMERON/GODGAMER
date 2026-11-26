
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = None


def start_scheduler():
    """Start the background scheduler."""
    global scheduler

    if scheduler is not None and scheduler.running:
        logger.info("Scheduler is already running.")
        return

    scheduler = AsyncIOScheduler(
        timezone="Asia/Kolkata"
    )

    scheduler.start()

    logger.info("Scheduler started successfully.")


def add_interval_job(
    function,
    minutes,
    job_id,
    args=None,
    replace_existing=True
):
    """Schedule a function to run at regular intervals."""

    if scheduler is None or not scheduler.running:
        raise RuntimeError("Scheduler is not running.")

    if minutes <= 0:
        raise ValueError("Interval must be greater than zero.")

    scheduler.add_job(
        function,
        trigger=IntervalTrigger(minutes=minutes),
        id=job_id,
        args=args or [],
        replace_existing=replace_existing,
        max_instances=1,
        coalesce=True
    )

    logger.info("Scheduled job: %s", job_id)


def remove_job(job_id):
    """Remove a scheduled job."""

    if scheduler is None or not scheduler.running:
        return False

    try:
        scheduler.remove_job(job_id)
        logger.info("Removed scheduled job: %s", job_id)
        return True

    except Exception:
        logger.exception("Could not remove job: %s", job_id)
        return False


def stop_scheduler():
    """Stop the scheduler safely."""
    global scheduler

    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    scheduler = None
