"""
Handles all the JWT operations for the magic link authentication flow.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from passlib.context import CryptContext

from app.core.config import JWT_SECRET, JWT_ALGORITHM

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    Returns a secure brcypt hash of the plaintext password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against the stored bcrypt hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_magic_link_token(user_id: str, flight_id: str, departure_time_utc: datetime, arrival_time_utc: datetime) -> str:
    """
    Create the JWT embedded in the email/sms magic link.
    """

    now = datetime.now(timezone.utc)

    if departure_time_utc.tzinfo is None:
        departure_time_utc = departure_time_utc.replace(tzinfo=timezone.utc)

    if arrival_time_utc.tzinfo is None:
        arrival_time_utc = arrival_time_utc.replace(tzinfo=timezone.utc)
    
    activation_time = departure_time_utc - timedelta(hours=4)
    expiration_time = arrival_time_utc + timedelta(hours=8)

    payload = {
        "sub": user_id,
        "flight_id": str(flight_id),
        "type": "magic_link",
        "nbf": int(activation_time.timestamp()),
        "exp": int(expiration_time.timestamp()),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_session_token(user_id: str, flight_id: str, thread_id: str, departure_time_utc: datetime, arrival_time_utc: datetime) -> str:
    """
    Create the active session JWT for the websocket chat connection.
    Issued only after the magic link has been verified.
    """

    now = datetime.now(timezone.utc)

    if arrival_time_utc.tzinfo is None:
        arrival_time_utc = arrival_time_utc.replace(tzinfo=timezone.utc)

    if departure_time_utc.tzinfo is None:
        departure_time_utc = departure_time_utc.replace(tzinfo=timezone.utc)

    activation_time = departure_time_utc - timedelta(hours=4)
    expiration_time = arrival_time_utc + timedelta(hours=6)

    nbf_time = min(activation_time, now)

    payload = {
        "sub" : user_id,
        "flight_id" : str(flight_id),
        "thread_id" : str(thread_id),
        "type" : "session",
        "nbf" : int(nbf_time.timestamp()),
        "exp" : int(expiration_time.timestamp()),
        "iat" : int(now.timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Decodes and validates the JWT
    Returns the dictionary with status and payload.
    """

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != expected_type:
            return {"valid": False, "error": "Invalid Token Type"}
        return {"valid": True, "payload": payload}
    
    except jwt.ImmatureSignatureError:
        return {"valid": False, "error": "Token will get activated 4 hrs before departure time"}
    
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token has been expired"}
    
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Invalid Token"}


def extract_user_and_flight(token:str , expected_type: str= "session") -> Optional[tuple[str,str]]:
    """
    Quick helper function for the Websocket and REST dependency injection.
    Returns (user_id, flight_id) if vlaid, else None
    """

    result = verify_token(token, expected_type)
    if result["valid"]:
        return result["payload"].get("sub"), result["payload"].get("flight_id")
    
    return None