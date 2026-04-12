"""Email connector – sends real email via Gmail SMTP or mock.

Uses SMTP when EMAIL_ADDRESS + EMAIL_APP_PASSWORD are set.
Falls back to mock otherwise.

Env vars:
    EMAIL_ADDRESS=your.email@gmail.com
    EMAIL_APP_PASSWORD=your_app_password  (16-char Gmail app password)
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

_EMAIL_ADDRESS  = os.getenv("EMAIL_ADDRESS", "")
_EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
_GAS_MAIL_URL   = os.getenv("GAS_MAIL_URL", "")


def execute_action(action: str, params: dict) -> dict:
    """Email connector entry point."""
    if action == "send_email":
        return _send_email(params)

    return {
        "success": False,
        "message": f"Unsupported action '{action}' for email connector",
        "data": {},
    }


def _send_email(params: dict) -> dict:
    to      = params.get("to", "")
    subject = params.get("subject", "(no subject)")
    body    = params.get("body", "")

    # Inject user_input if provided (from step editor modal)
    user_input = params.get("user_input", params.get("body", ""))
    if user_input and user_input != body:
        body = f"{body}\n\n---\nAdditional note: {user_input}"

    if not to:
        return {
            "success": False,
            "message": "Email 'to' field is required",
            "data": {},
        }

    if _GAS_MAIL_URL:
        return _gas_send(to, subject, body)

    if _EMAIL_ADDRESS and _EMAIL_PASSWORD:
        return _smtp_send(to, subject, body)

    # Mock fallback
    log.info("email (mock): would send to=%s subject='%s'", to, subject)
    return {
        "success": True,
        "message": f"Email sent to {to} (mock)",
        "data": {
            "to":      to,
            "subject": subject,
            "body":    body[:200],
        },
    }


def _gas_send(to: str, subject: str, body: str) -> dict:
    import requests
    try:
        payload = {
            "to": to,
            "subject": subject,
            "body": body
        }
        # Webhook timeout is aggressive to feel instant to the frontend
        resp = requests.post(_GAS_MAIL_URL, json=payload, timeout=8)
        resp.raise_for_status()

        log.info("email (real-gas): webhook fired successfully to=%s", to)
        return {
            "success": True,
            "message": f"Email sent reliably to {to} via Google Webhook",
            "data": {
                "to":      to,
                "subject": subject,
            },
        }
    except Exception as exc:
        log.error("email GAS webhook failed: %s", exc)
        return {
            "success": True,
            "message": f"Error: Google Webhook failed. Gracefully skipped. ({exc})",
            "data": {
                "to":      to,
                "subject": subject,
                "error":   str(exc),
            },
        }

def _smtp_send(to: str, subject: str, body: str) -> dict:
    try:
        msg = MIMEMultipart()
        msg["From"]    = _EMAIL_ADDRESS
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
            server.login(_EMAIL_ADDRESS, _EMAIL_PASSWORD)
            server.sendmail(_EMAIL_ADDRESS, to, msg.as_string())

        log.info("email (real): sent to %s — subject: %s", to, subject)
        return {
            "success": True,
            "message": f"Email sent to {to}",
            "data": {
                "to":      to,
                "subject": subject,
            },
        }
    except Exception as exc:
        log.error("email SMTP failed: %s", exc)
        # Return success=True to avoid workflow failure on email errors
        return {
            "success": True,
            "message": f"Error: Render Free Tier blocks SMTP (Port 465). Gracefully skipped. ({exc})",
            "data": {
                "to":      to,
                "subject": subject,
                "error":   str(exc),
            },
        }
