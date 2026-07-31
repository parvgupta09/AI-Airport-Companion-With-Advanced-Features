# We use redis pub/sub here so that even if we run the multiple FastAPI servers, all servers hear the alert and can notify the user.
# We also use websocket here to push the changes from flight_simulator instantly and without any lag

import logging
import json
from sqlalchemy.orm import Session
from app.database.postgres_models import Flight, FlightStatus
from app.database.postgres_session import SessionLocal
from app.services.flight_simulator import flight_simulator
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

async def poll_active_flights():
    """
    Polls active flights from PostreSQL, excecutes a simulation/status progression,
    and publishes real-time WebSocket alert triggers to Redis when gate changes or delays occus.
    """
    db: Session = SessionLocal()
    redis_client = await get_redis()

    try:
        active_flights = db.query(Flight).filter(Flight.status.notin_([FlightStatus.COMPLETED, FlightStatus.CANCELLED])).all()

        if not active_flights:
            return
        
        changes_made = False

        for flight in active_flights:
            try:
                old_gate = flight.gate.name if flight.gate else "Unassigned"
                old_delay = flight.delay_minutes
                old_status = flight.status.name

                modified = flight_simulator.process_flight(flight)

                if modified:
                    changes_made = True
                    new_gate = flight.gate.name if flight.gate else "Unassigned"
                    new_delay = flight.delay_minutes
                    new_status = flight.status.name

                    logger.info(f"Flight {flight.flight_number} (PNR: {flight.pnr}) updated -> Status: {new_status}, Gate: {new_gate}, Delay : {new_delay}")

                    alerts_triggered = []
                    if new_gate != old_gate and flight.gate_changed:
                        alerts_triggered.append(
                            f"EMERGENCY GATE CHANGE : Your flight {flight.flight_number} has moved to {new_gate}"
                        )
                    if new_delay > old_delay:
                        alerts_triggered.append(
                            f"FLIGHT DELAYED: Flight {flight.flight_number} is delayed by {new_delay} minutes."
                        )
                    if new_status == "BOARDING" and old_status != "BOARDING":
                        alerts_triggered.append(
                            f"NOW BOARDING: Flight {flight.flight_number} is now boarding at {new_gate}."
                        )

                    if alerts_triggered and flight.user_id:

                        combined_msg = " ".join(alerts_triggered)
                        event_payload = {
                            "user_id" : str(flight.user_id),
                            "type" : "flight_alert",
                            "message" : combined_msg,
                            "flight_number" : flight.flight_number,
                            "alerts_count" : len(alerts_triggered)
                        }
                        await redis_client.publish("airport:alerts", json.dumps(event_payload))

            except Exception as e:
                logger.error(f"Error processing flight {flight.flight_number}: {str(e)}")

        if changes_made:
            db.commit()

    except Exception as e:
        logger.error(f"Database error during flight polling job: {str(e)}")
        db.rollback()

    finally:
        db.close()