"""
Handles all the JWT operations for the magic link authentication flow.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt

from app.core.config import JWT_SECRET, JWT_ALGORITHM


def create_magic_link_token(user_id: str, flight_id: str, departure_time_utc: datetime) -> str:
    """
    Create the JWT embedded in the email/sms magic link.
    """

    activation_time = departure_time_utc - timedelta(hours=4)
    expiration_time = departure_time_utc + timedelta(hours=24)
    payload = {
        "sub": user_id,
        "flight_id": str(flight_id),
        "type": "magic_link",
        "nbf": activation_time,
        "exp": expiration_time,
        "iat": datetime.utcnow(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_session_token(user_id: str, flight_id: str, thread_id: str, departure_time_utc: datetime) -> str:
    """
    Create the active session JWT for the websocket chat connection.
    Issued only after the magic link has been verififed.
    """

    expiration_time = departure_time_utc + timedelta(hours=24)
    payload = {
        "sub" : user_id,
        "flight_id" : str(flight_id),
        "thread_id" : str(thread_id),
        "type" : "session",
        "exp" : expiration_time,
        "iat" : datetime.utcnow(timezone.utc)
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
        return {"valid": False, "error": "Token will get activaated 4 hrs before departure time"}
    
    except jwt.ExpiredSignatureError:
        return {"valid": False, "error": "Token has been expired"}
    
    except jwt.InvalidTokenError:
        return {"valid": False, "error": "Invalid Token"}


def extract_user_and_flight(token:str , expected_type: str= "session") -> Optional[tuple]:
    
    result = verify_token(token, expected_type)
    if result["valid"]:
        return result["payload"].get("sub"), result["payload"].get("flight_id")
    
    return None