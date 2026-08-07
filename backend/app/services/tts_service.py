import logging
import base64
import requests
from typing import Optional
from app.core.config import SARVAM_API_KEY

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        self.api_key = SARVAM_API_KEY
        self.enabled = bool(self.api_key)
        self.url = "https://api.sarvam.ai/text-to-speech"

    def text_to_speech(self, text: str, speaker: str = "shubh") -> Optional[bytes]:
        """
        Converts the AI text response to WAV audio bytes using Sarvam AI Bulul model.
        """

        if not self.enabled:
            logger.warning("API key missing. TTS Service diabled")
            return None

        clean_text = text.strip()[:500]
        if not clean_text:
            return None

        try:
            headers = {
                "api-subscription-key": self.api_key,
                "Content-Type": "application/json"
            }

            payload = {
                "inputs": [clean_text],
                "target_language_code": "en_IN",
                "speaker": speaker,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.5,
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
                "model": "bulbul:v3"
            }

            logger.info(f"Generating Sarvam TTS audio for text: '{clean_text[:40]}...'")
            response = requests.post(self.url, headers=headers, json=payload, timeout=15)
            response.raise_for_status()

            result = response.json()
            audios = result.get("audios",[])

            if not audios:
                logger.error("Sarvam TTS returned an empty audios list.")
                return None

            audio_base64 = audios[0]
            audio_bytes = base64.b64decode(audio_base64)

            logger.info(f"Sarvam TTS generated {len(audio_bytes)} audio bytes successfully.")
            return audio_bytes

        except requests.exceptions.RequestException as e:
            logger.error(f"Sarvam AI TTS API error: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Sarvam response details: {e.response.text}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error in TTSService: {str(e)}", exc_info=True)
            return None

tts_service = TTSService()