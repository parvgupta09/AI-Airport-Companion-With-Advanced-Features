import logging
from sqlalchemy.orm import Session
from app.database.postgres_models import Flight, FlightStatus
from app.database.postgres_session import SessionLocal
from app.services.flight_simulator import flight_simulator

logger = logging.getLogger(__name__)

def poll_active_flights():

    db: Session = SessionLocal()
    try:
        active_flights = db.query(Flight).filter(Flight.status.notin_([FlightStatus.COMPLETED, FlightStatus.CANCELLED])).all()

        if not active_flights:
            return
        
        changes_made = False

        for flight in active_flights:
            try:
                modified = flight_simulator.process_flight(flight)

                if modified:
                    changes_made = True
                    logger.info(f"Flight {flight.flight_number} updated. Status: {flight.status.name}, Gate: {flight.gate.name if flight.gate else 'None'}")

            except Exception as e:
                logger.error(f"Error processing flight {flight.flight_number}: {str(e)}")

        if changes_made:
            db.commit()

    except Exception as e:
        logger.error(f"Database error during flight polling job: {str(e)}")
        db.rollback()

    finally:
        db.close()