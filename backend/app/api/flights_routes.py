import logging
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.database.postgres_models import User, Flight
from app.database.postgres_session import get_db
from app.services.flight_generator import flight_generator

class PassengerRegistrationRequest(BaseModel):
    pnr: str = Field(..., min_length=6, max_length=6, description="6-character alphanumeric PNR")
    name: str = Field(..., description="Passenger's full name")
    email: EmailStr = Field(..., description="Passengers's email address")
    phone_number: str = Field(..., description="Passenger's mobile number for SMS")
    source: str = Field(..., description="Origin airport code (e.g., DEL)")
    destination: str = Field(..., description="Destination airport code (e.g., DEL)")
    departure_time_utc: datetime = Field(..., description="Scheduled departure time in UTC")

class PassengerRegistrationResponse(BaseModel):
    success: bool
    message: str
    pnr: str
    flight_number: str

class FlightStatusResponse(BaseModel):
    pnr: str
    flight_number: str
    status: str
    gate: str | None
    terminal: str | None
    delay_minutes: int

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/flights", tags=["Flights"])

@router.post("/register", response_model=PassengerRegistrationResponse)
async def register_passenger(payload: PassengerRegistrationRequest, db: Session=Depends(get_db)):
    """
    Registers a new passenger, generates their synthetic flight data, and saves the itinerary to PostgreSQL
    """

    clean_pnr = payload.pnr.strip().upper()
    if not re.match(r"^[A-Z0-9]{6}", clean_pnr):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PNR format. PNR must be exactly 6 alphanumeric characters.")

    existing_flight = db.query(Flight).filter(Flight.pnr == clean_pnr).first()
    if existing_flight:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This PNR is already registered in the system.")

    try:
        user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
        if not user:
            user = User(
                name = payload.name.strip(),
                email = payload.email.lower().strip(),
                phone_number = payload.phone_number.strip()
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        else:
            user.phone_number = payload.phone_number.strip()
            db.commit()

        flight_data = flight_generator.generate_flight(
            pnr = clean_pnr,
            source = payload.source.strip().upper(),
            destination = payload.destination.strip().upper(),
            departure_time = payload.departure_time_utc
        )

        new_flight = Flight(
            user_id = user.id,
            pnr = flight_data["pnr"],
            leg_number = flight_data["leg_number"],
            source = flight_data["source"],
            destination = flight_data["destination"],
            flight_number = flight_data["flight_number"],
            airline = flight_data["airline"],
            aircraft = flight_data["aircraft"],
            terminal = flight_data["terminal"],
            gate=flight_data["gate"],
            departure_time_utc=flight_data["departure_time_utc"],
            arrival_time_utc=flight_data["arrival_time_utc"],
            boarding_time_utc=flight_data["boarding_time_utc"],
            layover_duration_minutes=flight_data["layover_duration_minutes"],
            baggage_belt=flight_data["baggage_belt"],
            has_layover=flight_data["has_layover"],
            layover_airport=flight_data["layover_airport"],
            is_international=flight_data["is_international"],
            status=flight_data["status"],
        )

        db.add(new_flight)
        db.commit()
        db.refresh(new_flight)

        logger.info(f"Successfully registered PNR {clean_pnr} for User{user.name}")

        return PassengerRegistrationResponse(
            success = True,
            message = "Registration successful! You will recieve your check-in link 24 hourse before boarding via email and sms.",
            pnr = clean_pnr,
            flight_number = new_flight.flight_number
        )

    except Exception as e:
        logger.info(f"Error registering passenger: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occured while registering the user's flight data. Please check your airport.")


@router.get("/status/{pnr}", response_model=FlightStatusResponse)
async def get_flight_status(pnr: str, db: Session = Depends(get_db)):
    """
    Returns the real time status of a passenger's flight.
    Useful for the frontend to show a quick status dashboard before they open chat.
    """

    clean_pnr = pnr.strip().upper()
    flight = db.query(Flight).filter(Flight.pnr == clean_pnr).first()

    if not flight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found for the given PNR.")

    return FlightStatusResponse(
        pnr = flight.pnr,
        flight_number = flight.flight_number,
        status = flight.status.name if flight.status else "SCHEDULED",
        gate = flight.gate.value if flight.gate else "Unassigned",
        terminal = flight.terminal.value if flight.terminal else "Unassigned",
        delay_minutes = flight.delay_minutes
    )