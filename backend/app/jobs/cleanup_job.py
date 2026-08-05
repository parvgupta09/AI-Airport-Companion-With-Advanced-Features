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
        
        # Deleting all the reminders as and when they gets completed
        rem_res = db.query(Reminder).filter(Reminder.is_sent == True).delete(synchronize_session=False)
        logger.info(f"Deleted {rem_res} sent reminders.")

        # Identifying expired users
        expired_flights = db.query(Flight).filter(
            Flight.status.in_([FlightStatus.COMPLETED, FlightStatus.CANCELLED]),
            (Flight.arrival_time_utc < cutoff_time)
        ).all()

        expired_user_ids = {flight.user_id for flight in expired_flights if flight.user_id}
        expired_thread_ids = [flight.thread_id for flight in expired_flights if flight.thread_id]

        # Clean up langgraph checkpoint tables
        if expired_thread_ids:
            try:
                placeholders = ", ".join([f":t{i}" for i in range(len(expired_thread_ids))])
                params = {f"t{i}": tid for i, tid in enumerate(expired_thread_ids)}

                db.execute(text(f"DELETE FROM checkpoint_writes WHERE thread_id IN ({placeholders})"), params)
                db.execute(text(f"DELETE FROM checkpoint_blobs WHERE thread_id IN ({placeholders})"), params)
                db.execute(text(f"DELETE FROM checkpoints WHERE thread_id IN ({placeholders})"), params)
                logger.info(f"Purged LangGraph memory for {len(expired_thread_ids)} expired threads.")

            except Exception as table_err:
                logger.debug(f"LangGraph checkpoint cleanup skipped: {str(table_err)}")

        # Delete expired users(cascade flights)
        if expired_user_ids:
            users_to_delete = db.query(User).filter(User.id.in_(expired_user_ids)).all()
            for user in users_to_delete:
                db.delete(user)

            logger.info(f"Purged {len(users_to_delete)} users and their flight details (>48hrs post-completion).")

        db.commit()

        # Now cleaning the non TTL keys
        swept_keys = 0
        async for key in redis_client.scan_iter("airport:temp:*"):
            ttl = await redis_client.ttl(key)
            if ttl == -1:
                await redis_client.delete(key)
                swept_keys += 1

    except Exception as e:
        logger.error(f"Error executing cleanup task: {str(e)}", exc_info=True)
        db.rollback()

    finally:
        db.close()