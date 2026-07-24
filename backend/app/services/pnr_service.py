# This is the tool that will be used for the valdation of the pnr number entered by the user

import logging
import re
from sqlalchemy.orm import Session
from app.database.postgres_models import Flight

logger = logging.getLogger(__name__)

def validate_user(db: Session, pnr: str) -> str:
    """
    Validates if a 6-character Passenger Name Record (NR) exisits in the database.
    Use this tool when a user tries to check-in or asks about their flights using a PNR Code.

    Args:
        pnr: 6-character alphanumeric code (e.g., 'A1B2C3')
    """
    
    clean_pnr = pnr.strip().upper()

    if re.match(r"^[A-Z0-9]{6}$", clean_pnr):
        return clean_pnr

    logger.warning(f"Invalid PNR format attempted: {clean_pnr}")
    return None

def check_existing_flight(db: Session, clean_pnr: str) -> Flight | None:
    """
    Checks if the flight already exisits in the local PostgreSQL database
    """

    try:
        flight = db.query(Flight).filter(Flight.pnr == clean_pnr).first()
        return flight

    except Exception as e:
        logger.error(f"Error during pnr lookup: {str(e)}")
        return None