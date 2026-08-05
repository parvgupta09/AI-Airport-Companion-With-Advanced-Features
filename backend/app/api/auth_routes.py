"""
Handles the passwordless magic link authentication flow.
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database.postgres_session import get_db
from app.database.postgres_models import Flight
from app.services.weather_service import weather_service
from app.core.config import FRONTEND_URL
from app.core.security import(
    create_magic_link_token,
    create_session_token,
    verify_token
)
from app.services.email_service import email_service
from app.services.sms_service import sms_service
from app.services.pnr_service import validate_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=['Authentication'])

class MagicLinkRequest(BaseModel):
    pnr: str = Field(..., min_length=6, max_length=6, description="6-characters alpha numeric PNR")
    email: EmailStr = Field(..., description="Passenger's registered email address")

class MagicLinkResponse(BaseModel):
    success: bool
    message: str
    pnr: str

class VerifyTokenResponse(BaseModel):
    success: bool
    message: str
    session_token: str | None = None
    user_id: str | None = None
    flight_id: str | None = None
    thread_id: str | None = None


@router.post("/request-magic-link", response_model=MagicLinkResponse)
async def request_magic_link(payload:MagicLinkRequest, db:Session=Depends(get_db)):
    """
    Validates passenger's PNR and email, generates a timed JWT magic link and dispatches it via email/SMS.
    """

    clean_pnr = validate_user(db, payload.pnr)
    if not clean_pnr:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid PNR format. PNR must be a 6 digit alphanumeric character.")

    flight = db.query(Flight).filter(Flight.pnr == clean_pnr).first()
    if not flight or not flight.user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active flights found for this PNR.")

    if flight.user.email.strip().lower() != payload.email.strip().lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The email address provided does not match the passenger record for this PNR.")

    # 24hrs check : Is boarding more than 24hrs away?
    now = datetime.now(timezone.utc)

    boarding_time = (
        flight.boarding_time_utc.replace(tzinfo=timezone.utc)
        if flight.boarding_time_utc.tzinfo is None
        else flight.boarding_time_utc
    )

    send_window_start = boarding_time - timedelta(hours=24)

    if now<send_window_start:
        logger.info(f"PNR {clean_pnr} requested link early. Boarding is >24hrs away.")
        return MagicLinkResponse(
            success = True,
            message = "Registered successfully. You will be getting a session link 24hrs before your boarding.",
            pnr = clean_pnr
        )

    # Within 24hrs : Generate Token and dispatch Email/SMS
    magic_token = create_magic_link_token(
        user_id=str(flight.user_id),
        flight_id=str(flight.id),
        departure_time_utc=flight.departure_time_utc,
        arrival_time_utc=flight.arrival_time_utc
    )

    frontend_verify_url = f"{FRONTEND_URL}/verify?token={magic_token}"

    destination_weather = weather_service.get_weather_for_destination(flight.destination)

    html_content = (
        f"<h3>Your Airport Companion Magic Link</h3>"
        f"<p>Hello <b>{flight.user.name}</b>,</p>"
        f"<p>Your flight <b>{flight.flight_number}</b> ({flight.source} &rarr; {flight.destination}) is boarding soon!</p>"
        f"<p><b>Destination Weather Update:</b> {destination_weather} (Pack accordingly!)</p>"
        f"<p>Click the button below to access your live AI assistant and terminal companion:</p>"
        f"<p><a href='{frontend_verify_url}' style='background:#0052cc;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;'>Open Airport Companion</a></p>"
        f"<p><i>Note: Interactive chat unlocks exactly 4 hours prior to your scheduled departure time.</i></p>"
    )

    sms_body = (
        f"AI Companion Check-In for flight {flight.flight_number} : {frontend_verify_url}"
    )

    email_sent, sms_sent = await asyncio.gather(
        asyncio.to_thread(
            email_service.send_email,
            to_email = flight.user.email,
            subject=f"Check-In Link: Flight {flight.flight_number} to {flight.destination}",
            html_content=html_content
        ),
        asyncio.to_thread(
            sms_service.send_message,
            to_phone=flight.user.phone_number,
            body=sms_body
        )
    )

    if not email_sent and not sms_sent:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to dispatch magic link email or sms. Plase try again.")

    flight.magic_link_sent = True
    db.commit()

    logger.info(
        f"Magic Link dispatched successfully for PNR {clean_pnr} to {flight.user.email} and {flight.user.phone_number}"
    )

    return MagicLinkResponse(
        success=True,
        message="Magic link sent to your email address and phone number.",
        pnr = clean_pnr
    )

@router.get("/verify-magic-link", response_model=VerifyTokenResponse)
async def verify_magic_link(token: str = Query(..., description="The JWT magic link token from email or sms"), db:Session=Depends(get_db)):
    """
    Validates the magic link JWT. If clicked before 4hr pre-deprature window, return a clean error message. If valid then issues an active session token for Websockets.
    """

    result = verify_token(token, expected_type="magic_link")

    if not result["valid"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=result["error"])

    payload = result["payload"]
    user_id = payload.get("sub")
    flight_id = payload.get("flight_id")

    flight = db.query(Flight).filter(Flight.id == flight_id).first()
    if not flight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight session no longer exists.")

    if not flight.thread_id:
        flight.thread_id = f"thread_{flight.pnr}_{user_id[:8]}"
        db.commit()

    session_token = create_session_token(
        user_id=str(user_id),
        flight_id=str(flight_id),
        thread_id=str(flight.thread_id),
        departure_time_utc=flight.departure_time_utc,
        arrival_time_utc=flight.arrival_time_utc
    )

    logger.info(f"Magic Link verified for user {user_id}. Session token issued.")
    return VerifyTokenResponse(
        success=True,
        message="Check-In verified. Welcome to your Airport Companion",
        session_token=session_token,
        user_id=str(user_id),
        flight_id=str(flight_id),
        thread_id=str(flight.thread_id)
    )