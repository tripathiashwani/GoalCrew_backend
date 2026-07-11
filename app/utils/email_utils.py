import smtplib
from email.mime.text import MIMEText
import logging
from app.config import Config

config = Config()

from app.utils.logger import get_logger
logger = get_logger("UserService")

def send_email(to_email: str, subject: str, body: str):
    """
    Send an email with error handling and logging.
    """
    try:
        msg = MIMEText(body, "html")
        msg["Subject"] = subject
        msg["From"] = f"{config.EMAILS_FROM_NAME} <{config.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email

        logger.info(f"[EMAIL] Attempting to send email to {to_email} via {config.SMTP_HOST}:{config.SMTP_PORT}")

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.EMAILS_FROM_EMAIL, [to_email], msg.as_string())

        logger.info(f"[EMAIL] Successfully sent email to {to_email} with subject '{subject}'")

    except smtplib.SMTPException as smtp_err:
        logger.exception(f"[EMAIL] SMTP error while sending to {to_email}: {smtp_err}")
        raise
    except Exception as e:
        logger.exception(f"[EMAIL] Failed to send email to {to_email}: {e}")
        raise
