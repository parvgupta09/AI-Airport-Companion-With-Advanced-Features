import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.jobs.flight_poll_job import poll_active_flights
from app.jobs.cleanup_job import run_cleanup_job
from app.jobs.notification_job import start_notification_listener, dispatch_due_magic_links
from app.jobs.reminder_jobs import process_reminders
from app.jobs.weather_job import fetch_airport_weather

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
_notification_task : asyncio.Task | None = None

def start_scheduler() -> AsyncIOScheduler:
    """
    
    """

    global _notification_task

    if scheduler.running:
        logger.warning("Scheduler instance is already running.")
        return scheduler

    scheduler.add_job(
        poll_active_flights,
        trigger=IntervalTrigger(seconds = 10),
        id="flight_poller",
        name="Poll Active Flight Statuses and Gate Changes",
        replace_existing = True,
        coalesce=True,
        max_instances=1
    )

    scheduler.add_job(
        fetch_airport_weather,
        trigger=IntervalTrigger(hours = 1),
        id="weather_processor",
        name="Fetch Dynamic Airport and Destination Weather",
        replace_existing = True
    )

    scheduler.add_job(
        process_reminders,
        trigger=IntervalTrigger(seconds = 5),
        id="reminder_processor",
        name="Process Due Passenger Reminders from Redis ZSET",
        replace_existing=True,
        coalesce=True,
        max_instances=1
    )

    scheduler.add_job(
        run_cleanup_job,
        trigger=IntervalTrigger(hours=24),
        id="database_cleanup",
        name="Purge Expired Checkpoints and Completed Records",
        replace_existing=True
    )

    scheduler.add_job(
        dispatch_due_magic_links,
        trigger=IntervalTrigger(minutes=15),
        id="magic_link_dispatcher",
        name="Auto-dispatch Magic Links for Flights within 24 Hours",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("APScheduler initiated successfully with background polling jobs active.")

    loop = asyncio.get_running_loop()
    if not _notification_task or _notification_task.done():
        _notification_task = loop.create_task(start_notification_listener())
        logger.info("Async Redis Pub/Sub Websocket notification listener task started.")

    return scheduler

def shutdown_scheduler() -> None:
    """
    Shut downs the APScheduler instance and cancels the async notification listener.
    """

    global _notification_task

    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shutdown successfully.")

    if _notification_task and not _notification_task.done():
        _notification_task.cancel()
        logger.info("Cancelled background notification listener task.")