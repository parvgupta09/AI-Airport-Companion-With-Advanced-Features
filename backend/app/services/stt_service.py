import logging
import io
import requests
from typing import Optional
from app.core.config import SARVAM_API_KEY

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        self.api_key = SARVAM_API_KEY
        self.enabled = bool(self.api_key)
        self.url = "https://api.sarvam.ai/speech-to-text"

    def transcribe_audio(self, audio_bytes: bytes, filename: str = "recording.wav") -> Optional[str]:
        """
        Transcribes audio bytes to text using Sarvam AI Saaras model.
        """

        if not self.enabled:
            logger.warning("SARVAM_API_KEY missing. STT Service disabled.")
            return None
        
        try:
            headers = {
                "api-subscription-key": self.api_key
            }

            files = {
                "file": (filename, io.BytesIO(audio_bytes), "audio/wav")
            }

            data = {
                "model": "saaras:v3",
                "langauge_code": "en_IN",
                "with_timings": "false"
            }

            logger.info(f"Sending {len(audio_bytes)} bytes to Sarvam AI STT ({filename})...")
            response = requests.post(self.url, headers=headers, files=files, data=data, timeout=15)
            response.raise_for_status()

            result = response.json()
            transcript = result.get("transcript", "").strip()

            logger.info(f"Sarvam STT Transcription successful: '{transcript}'")
            return transcript

        except requests.exceptions.RequestException as e:
            logger.error(f"Sarvam AI STT API error : {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.info(f"Sarvam response details: {e.response.text}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in STTService: {str(e)}", exc_info=True)
            return None

stt_service = STTService()