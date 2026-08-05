import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from app.core.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER

logger = logging.getLogger(__name__)

class SMSService:
    def __init__(self):
        self.enabled = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)

        if self.enabled:
            self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            self.from_number = TWILIO_PHONE_NUMBER

        else:
            logger.warning("Twilio credentials missing. SMS Service runnning in terminal mode.")

    def send_message(self, to_phone: str, body: str) -> bool:
        if not self.enabled:
            logger.info(f"To: {to_phone} | Message: {body}")
            return True
        
        try:
            message = self.client.messages.create(
                body = body,
                from_  = self.from_number,
                to = to_phone
            )
            logger.info(f"SMS sent to {to_phone}. Message SID: {message.sid}")
            return True
        except TwilioRestException as e:
            logger.error(f"Failed to send SMS to {to_phone} : {str(e)}")
            return False
        
sms_service = SMSService()