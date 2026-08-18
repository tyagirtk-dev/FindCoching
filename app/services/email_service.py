"""
SMTP email sending. Credentials are pulled from the admin-editable SystemSetting
table (via settings_service) — never hardcoded and never from a fixed config file.
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.services.settings_service import get_setting

logger = logging.getLogger(__name__)


class EmailNotConfigured(Exception):
    pass


def _get_smtp_config():
    host = get_setting("SMTP_HOST")
    port = get_setting("SMTP_PORT")
    username = get_setting("SMTP_USERNAME")
    password = get_setting("SMTP_PASSWORD")
    sender_email = get_setting("SMTP_SENDER_EMAIL")
    sender_name = get_setting("SMTP_SENDER_NAME", "LocalTutor")
    use_tls = str(get_setting("SMTP_USE_TLS", "True")) == "True"

    if not host or not sender_email:
        raise EmailNotConfigured("SMTP is not configured. Set it from Admin Panel > SMTP Settings.")

    return {
        "host": host,
        "port": int(port or 587),
        "username": username,
        "password": password,
        "sender_email": sender_email,
        "sender_name": sender_name,
        "use_tls": use_tls,
    }


def send_email(to_email: str, subject: str, html_body: str, text_body: str = None):
    cfg = _get_smtp_config()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{cfg['sender_name']} <{cfg['sender_email']}>"
    msg["To"] = to_email

    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            if cfg["use_tls"]:
                server.starttls()
            if cfg["username"] and cfg["password"]:
                server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["sender_email"], [to_email], msg.as_string())
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        raise


def send_otp_email(to_email: str, name: str, code: str, purpose_label: str, expiry_minutes: int):
    subject = f"Your {purpose_label} code"
    html_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto;">
      <h2>Hi {name},</h2>
      <p>Your {purpose_label.lower()} code is:</p>
      <p style="font-size: 32px; font-weight: bold; letter-spacing: 4px;">{code}</p>
      <p>This code expires in {expiry_minutes} minutes. If you did not request this, you can ignore this email.</p>
    </div>
    """
    text_body = f"Your {purpose_label.lower()} code is {code}. It expires in {expiry_minutes} minutes."
    return send_email(to_email, subject, html_body, text_body)
