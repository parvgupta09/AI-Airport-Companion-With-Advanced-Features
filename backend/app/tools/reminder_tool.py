import logging
from datetime import datetime, timedelta, timezone
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.database.postgres_session import SessionLocal
from app.database.postgres_models import Reminder

logger = logging.getLogger(__name__)

@tool
def schedule_passenger_reminder(user_id: str, task_description: str, minutes_from_now: int) -> str:
    """
    Schedules an alert for the passenger.

    Args:
        user_id: The UUID of the current user.
        task_description: What to remind them about (e.g., 'Boarding starts soon', 'Pick up duty-free')
        minutes_from_now: How many minutes from now to send the alert.
    """

    db: Session = SessionLocal()

    try:
        trigger_time = datetime.now(timezone.utc) + timedelta(minutes = minutes_from_now)

        new_reminder = Reminder(
            user_id = user_id,
            task_description = task_description,
            trigger_time_utc = trigger_time,
            is_sent = False
        )

        db.add(new_reminder)
        db.commit()

        time_str = trigger_time.strftime("%H:%M UTC")
        logger.info("Scheduled reminder for user {user_id} at time {time_str}")

        return(
            f"Successfully scheduled a reminder for: '{task_description}'. "
            f"The system will alert the passenger in {minutes_from_now} minutes (at {time_str})."
        )

    except Exception as e:
        logger.error(f"Failed to set reminder in databse: {str(e)}")
        db.rollback()
        return "There was an internal databse error scheduling the reminder. Please try again in a moment."

    finally:
        db.close()