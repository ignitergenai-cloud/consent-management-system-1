"""Resend email client (replaces AWS SES)."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()

_RESEND_URL = "https://api.resend.com/emails"


async def send_email(
    *,
    api_key: str,
    to: str,
    subject: str,
    html: str,
    from_email: str = "onboarding@resend.dev",
) -> str | None:
    """Send an email via Resend. Returns message ID or None on failure."""
    if not api_key:
        logger.warning("resend_api_key_not_set", to=to, subject=subject)
        return None
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"from": from_email, "to": [to], "subject": subject, "html": html},
            )
            r.raise_for_status()
            msg_id = r.json().get("id")
            logger.info("email_sent", to=to, message_id=msg_id)
            return msg_id
    except Exception as exc:
        logger.error("email_send_failed", to=to, error=str(exc))
        return None
