# This is used when user explicitly asks something about his flight using his pnr number this has no realation to the direct alerts

import logging
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.database.postgres_session import SessionLocal
from app.database.postgres_models import Flight

logger = logging.getLogger(__name__)

@tool
def get_flight_status(flight_number: str) -> str:
    """
    Fetches the real-time status, gate, destination, and departure time, and other deatils of the flight for a specific flight.
    Use this whenever the person asks about flight delays, gate assignments, flight terminals, flight schedules, layovers, or baggage claims.

    Args:
        flight_number: The flight identifier (e.g., 'EK302', 'AI888')
    """

    logger.info(f"Checking the flight staus of flight number {flight_number}")
    db: Session = SessionLocal()
    try:
        flight = db.query(Flight).filter(Flight.flight_number == flight_number).first()

        if not flight:
            return f"I couldn't find any active flight with records for {flight_number}. Please check the flight number and try again."

        status_name = flight.status.name if flight.status else "SCHEDULED"
        gate_info = flight.gate.name if flight.gate else "Not assigned yet"
        terminal_info = flight.terminal.name if flight.terminal else "Not assigned yet"
        layover_info = f"Yes, at {flight.layover_airport}" if flight.has_layover else "No"

        return (
            f"--- FLIGHT MANIFEST FOR {flight.flight_number} ---\n"
            f"Route: {flight.source} -> {flight.destination} ({'International' if flight.is_international else 'Domestic'})\n"
            f"Airline: {flight.airline} | Aircraft: {flight.aircraft}\n"
            f"Status: {status_name} (Delayed by: {flight.delay_minutes} minutes)\n"
            f"Departure Location: Terminal {terminal_info}, Gate {gate_info}\n"
            f"Gate Changed Recently: {'Yes' if flight.gate_changed else 'No'}\n"
            f"Boarding Announced: {'Yes' if flight.boarding_announced else 'No'}\n\n"
            f"--- TIME SCHEDULE ---\n"
            f"Delay Duration: {flight.delay_minutes} minutes\n"
            f"New Boarding (if delay): {flight.boarding_time_utc}\n"
            f"New Departure (if delay): {flight.departure_time_utc}\n"
            f"Arrival Time: {flight.arrival_time_utc}\n\n"
            f"--- POST-FLIGHT & CONNECTIONS ---\n"
            f"Baggage Claim: Belt {flight.baggage_belt or 'Not Assigned Yet'}\n"
            f"Connecting/Layover Flight: {layover_info}\n"
        )


    except Exception as e:
        logger.error(f"Error in Database : {str(e)}")
        return "Your flight number is currently unreachable. Please try in a moment."

    finally:
        db.close()