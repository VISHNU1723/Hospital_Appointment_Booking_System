from dotenv import load_dotenv
import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)
load_dotenv()


def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send an email. Log failures without crashing the main operation."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM", smtp_user or "")

    if not smtp_user or not smtp_password:
        logger.error("Email not sent: SMTP_USER or SMTP_PASSWORD is missing.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        logger.info("Email sent successfully to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        return False
