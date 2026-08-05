import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:

    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Required environment variable {key} is not set. Please check your .env file.")
    return value

DATABASE_URL = _require("DATABASE_URL")

QDRANT_API_KEY = _require("QDRANT_API_KEY")
QDRANT_URL = _require("QDRANT_URL")
QDRANT_COLLECTION_NAME = _require("QDRANT_COLLECTION_NAME")

GEMINI_API_KEY = _require("GEMINI_API_KEY")

SARVAM_API_KEY = _require("SARVAM_API_KEY")
# ELEVENLABS_API_KEY = _require("ELEVENLABS_API_KEY")
# ELEVENLABS_VOICE_ID = _require("ELEVENLABS_VOICE_ID")

SENDGRID_API_KEY = _require("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = _require("SENDGRID_FROM_EMAIL")

TWILIO_ACCOUNT_SID = _require("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = _require("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = _require("TWILIO_PHONE_NUMBER")

OPENWEATHER_API_KEY = _require("OPENWEATHER_API_KEY")

JWT_SECRET = _require("JWT_SECRET")
JWT_ALGORITHM = _require("JWT_ALGORITHM")
JWT_EXPIRY_HOURS = int(_require("JWT_EXPIRY_HOURS"))

AIRPORT_NAME = _require("AIRPORT_NAME")

LANGSMITH_API_KEY = _require("LANGSMITH_API_KEY")
LANGCHAIN_TRACING_V2 = _require("LANGCHAIN_TRACING_V2")
LANGCHAIN_PROJECT = _require("LANGCHAIN_PROJECT")

FRONTEND_URL = _require("FRONTEND_URL")

ENVIRONMENT = _require("ENVIRONMENT")