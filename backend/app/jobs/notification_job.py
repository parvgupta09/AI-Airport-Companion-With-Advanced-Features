# We use Redis here as a pub/sub listner. It subscribes to the "airport:alerts" channel where flight_poll and reminder_job publish their events
# We use websockets here as a dispatcher. Its job it to take the events form the Redis and push it over into the WebSocket directly to the react frontend

import logging
import json
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.core.redis_client import get_redis
from app.core.config import FRONTEND_URL
from app.core.security import create_magic_link_token
from app.core.websocket_manager import manager
from app.database.postgres_session import SessionLocal
from app.database.postgres_models import User, Flight
from app.services.email_service import email_service
from app.services.sms_service import sms_service
from app.services.weather_service import weather_service

logger = logging.getLogger(__name__)

def get_user_contact(user_id: str) -> tuple[str | None, str | None]:
    """
    Synchronous helper function to fetch user email and phone number from PostgreSQL.
    Run via asyncio.to_thread to prevent blocking the async loop.
    """
    db: Session = SessionLocal()

    try:
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if user:
            return user.email, getattr(user, "phone_number", None)
        return None,None

    except Exception as e:
        logger.info(f"Failed to fetch contact into for user {user_id}: {str(e)}")
        return None, None

    finally:
        db.close()

async def start_notification_listener() -> None:
    """
    Long running background task that subscribes to the redis pub/sub 'airport:alerts' channel,
    pushes live WebSocket updates and enforces the Two-Tier Email/SMS fallback.
    """

    redis_client = await get_redis()
    pubsub = redis_client.pubsub()

    try:
        await pubsub.subscribe("airports:alerts")
        logger.info("Subscribed to Redis Pub/Sub channel 'airport:alerts' for WebSocket and SMS/Email dispatch.")

        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message and message["type"] == "message":
                try:
                    payload = json.loads(message["data"])
                    user_id = payload.get("user_id")
                    alert_type = payload.get("type")
                    message_text = payload.get("message")

                    if user_id and message_text:
                        delivered = await manager.send_personal_message(user_id, payload)
                        if delivered:
                            logger.debug(f"Pushed live WebSocket alert to user {user_id}: '{message_text}'")
                        else:
                            logger.debug(f"User {user_id} is offline on WebSocket.")

                        if alert_type == "flight_alert":
                            logger.info(f"Critical flight alert for user {user_id}. Dispatching SMS and Email...")
                            email, phone = await asyncio.to_thread(get_user_contact, user_id)

                            if email:
                                html_body = f"<h3>Flight Status Update</h3><p><b>{message_text}</b></p>"
                                await asyncio.to_thread(
                                    email_service.send_email,
                                    to_email = email,
                                    subject = "URGENT: Flight Status Update",
                                    html_content=html_body
                                )

                            if phone:
                                await asyncio.to_thread(
                                    sms_service.send_message,
                                    to_phone=phone,
                                    body = f"FLIGHT ALERT: {message_text}"
                                )

                        elif alert_type=="reminder" and not delivered:
                            logger.info(f"User {user_id} offline. Routng reminder vis SMS fallback...")
                            _, phone = await asyncio.to_thread(get_user_contact, user_id)

                            if phone:
                                await asyncio.to_thread(
                                    sms_service.send_message,
                                    to_phone=phone,
                                    body=f"REMINDER: {message_text}"
                                )

                            if email:
                                html_body = f"<h3>Flight Reminder</h3><p><b>{message_text}</b><p>"
                                await asyncio.to_thread(
                                    email_service.send_email,
                                    to_email = email,
                                    subject = "REMINDER: Upcoming Flight Task",
                                    html_content = html_body
                                )

                except json.JSONDecodeError:
                    logger.error("Failed to decode JSON payload from 'airport:alerts' channel.")

                except Exception as dispatch_err:
                    logger.error(f"Error during notification deispatch: {str(dispatch_err)}",exc_info=True)

    except asyncio.CancelledError:
        logger.info("Notification listener background task cancelled.")
        await pubsub.unsubscribe("airport:alerts")
        await pubsub.close()

    except Exception as e:
        logger.error(f"Critical error in Redis notification listener: {str(e)}", exc_info=True)


async def dispatch_due_magic_links() -> None:
    """
    Runs automatically after every 15mins.
    Finds the flights boarding within the next 24hrs where magic_link_send == False
    """

    db: Session = SessionLocal()

    try:
        now = datetime.now(timezone.utc)
        window_start = now + timedelta(hours=24)

        due_flights = (
            db.query(Flight).filter(Flight.magic_link_sent==False, Flight.boarding_time_utc <= window_start, Flight.boarding_time_utc > now).all()
        )

        if not due_flights:
            return

        logger.info(f"Found {len(due_flights)} flight(s) entering the 24hr wondow. Dispatching magic links...")

        for flight in due_flights:
            if not flight.user:
                continue

            magic_token = create_magic_link_token(
                user_id = str(flight.user_id),
                flight_id = str(flight.flight_id),
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
                f"AI Companion Check-In for flight {flight.flight_number}: {frontend_verify_url}"
                f"Weather in {flight.destination}: {destination_weather}"
            )

            try:
                await asyncio.gather(
                    asyncio.to_thread(
                        email_service.send_email,
                        to_email=flight.user.email,
                        subject=f"Check-in link : Flight {flight.flight_number} to {flight.destination}",
                        html_content=html_content
                    ),
                    asyncio.to_thread(
                        sms_service.send_message,
                        to_phone=flight.user.phone_number,
                        body=sms_body
                    ),
                )

                flight.magic_link_sent = True
                logger.info(f"Auto-dispatched 24hrs magic link for PNR {flight.pnr} to {flight.user.email}")

            except Exception as dispatch_err:
                logger.error(f"Failed to auto-dispatch link for PNR {flight.pnr}: {str(dispatch_err)}")

        db.commit()

    except Exception as e:
        logger.error(f"Error in automatic 24hr magic link dispatcher job: {str(e)}")
        db.rollback()
    finally:
        db.close()
