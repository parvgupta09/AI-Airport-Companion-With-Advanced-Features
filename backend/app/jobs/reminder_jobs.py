# We use redis sorted sets here. Instead of querying PostgreSQL every time, reminders are stored in Redis Sorted Sets. The job pops reminders at the exact second thay are due.
# We use websocket here to push the reminders instantly as an when it is popped up by the redis

import logging
import json
import time
from sqlalchemy.orm import Session
from app.database.postgres_models import Reminder
from app.database.postgres_session import SessionLocal
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

REMINDER_ZSET_KEY = "airport:delayed_reminders"

async def process_reminders() -> None:
    redis_client = await get_redis()
    now_ts = time.time()

    try:
        due_items = await redis_client.zrangebyscore(
            REMINDER_ZSET_KEY,
            min = 0,
            max = now_ts,
            start = 0,
            num = 50
        )

        if not due_items:
            return

        # Atomic Removal of all the entries form the Redis Cache
        removed_count = await redis_client.zrem(REMINDER_ZSET_KEY, *due_items)

        if removed_count==0:
            return

        db: Session = SessionLocal()

        try:
            for item_json in due_items:
                reminder_data = json.loads(item_json)
                reminder_id = reminder_data.get("id")
                user_id = reminder_data.get("user_id")
                message = reminder_data.get("task_description")

                reminder_db = db.query(Reminder).filter(Reminder.id == reminder_id).first()
                if reminder_db and not reminder_db.is_sent:
                    reminder_db.is_sent = True
                    logger.info(f"Triggering reminder {reminder_id} for user {user_id}: '{message}'")

                    # Publishing to Redis pub/sub for immediate Websocket push
                    alert_payload = {
                        "user_id": str(user_id),
                        "type": "reminder",
                        "message": message
                    }
                    await redis_client.publish("airport:alerts", json.dumps(alert_payload))

            db.commit()
            logger.info(f"Processed and dispatched {len(due_items)} due passenger reminders.")

        except Exception as db_err:
            logger.error(f"Database error while updating reminders: {str(db_err)}.", exc_info=True)
            db.rollback()

            for item_json in due_items:
                await redis_client.zadd(REMINDER_ZSET_KEY, {item_json: now_ts})

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error reading from Redis reminders: {str(e)}", exc_info=True)