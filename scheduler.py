import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.base import JobLookupError

# Fix: name ki jagah name use karein
logger = logging.getLogger(name)

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    timezone="UTC"
)


def start_scheduler():
    """Start background scheduler (must be called inside an active event loop)."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started.")


def shutdown_scheduler():
    """Stop background scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")


def add_interval_job(
    func,
    seconds: int,
    job_id: str,
    replace_existing: bool = True,
    args: list = None,
    kwargs: dict = None
):
    """Register a recurring asynchronous job."""
    if seconds <= 0:
        raise ValueError("Interval must be greater than zero.")

    scheduler.add_job(
        func,
        trigger="interval",
        seconds=seconds,
        id=job_id,
        args=args,
        kwargs=kwargs,
        replace_existing=replace_existing,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30
    )
    logger.info("Scheduled job registered: %s", job_id)


def add_daily_job(
    func,
    hour: int,
    minute: int,
    job_id: str,
    args: list = None,
    kwargs: dict = None
):
    """Register a daily asynchronous job in UTC."""
    if not 0 <= hour <= 23:
        raise ValueError("Hour must be between 0 and 23.")

    if not 0 <= minute <= 59:
        raise ValueError("Minute must be between 0 and 59.")

    scheduler.add_job(
        func,
        trigger="cron",
        hour=hour,
        minute=minute,
        id=job_id,
        args=args,
        kwargs=kwargs,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60
    )
    logger.info("Daily job registered: %s", job_id)


def remove_job(job_id: str) -> bool:
    """Remove a scheduled job."""
    try:
        scheduler.remove_job(job_id)
        logger.info("Scheduled job removed: %s", job_id)
        return True
    except JobLookupError:
        logger.warning("Job not found: %s", job_id)
        return False


def get_scheduled_jobs():
    """Return all registered scheduled jobs."""
    return scheduler.get_jobs()
