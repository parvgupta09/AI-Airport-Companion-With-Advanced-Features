import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.core.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.enabled = bool(SENDGRID_API_KEY)

        if self.enabled:
            self.client = SendGridAPIClient(SENDGRID_API_KEY)
            self.from_email = SENDGRID_FROM_EMAIL
        
        else:
            logger.warning("SendGrid API key missing. Email Service running in terminal mode.")

    def send_email(self, to_email: str, subject: str, html_content: str) -> bool:

        if not self.enabled:
            logger.info(f"To: {to_email} | Subject: {subject} | Content: {html_content}")
            return True
        
        message = Mail(
            from_email = self.from_email,
            to_emails = to_email,
            subject = subject,
            html_content = html_content
        )

        try:
            response = self.client.send(message)
            logger.info(f"Email sent to {to_email}. Status Code: {response.status_code}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_email} : {str(e)}")
            return False
        
email_service = EmailService()
