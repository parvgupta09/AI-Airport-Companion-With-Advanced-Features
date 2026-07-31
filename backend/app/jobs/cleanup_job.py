import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from app.database.postgres_models import User, Flight, FlightStatus, Reminder
from app.database.postgres_session import SessionLocal
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

async def run_cleanup_job() -> None:
    """
    Deletes the completed reminders immediately, deletes users (and their flights) 48 hrs after flight completion, and sweeps orphaned Redis Keys.
    """

    logger.info("Starting scheduled 48-hour database and Redis ")

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)
    db = SessionLocal()
    redis_client = await get_redis()

    try:
        rem_res = db.query(Reminder).filter(Reminder.is_sent == True).delete(synchronize_session=False)
        