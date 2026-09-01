"""Template management endpoints for the Notification Service."""

import os
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, Response

from notification_service.config import NotificationServiceSettings
from notification_service.dependencies import get_settings

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.get("")
async def list_templates(
    settings: NotificationServiceSettings = Depends(get_settings),
) -> dict:
    """List all available notification templates.

    Scans the templates directory for SMS and email template files and
    returns them grouped by channel type.

    Args:
        settings: The notification service settings.

    Returns:
        A dictionary containing lists of available templates by channel.
    """
    templates: dict[str, list[dict[str, str]]] = {"sms": [], "email": []}

    # Resolve the templates directory relative to the notification_service package
    package_dir = Path(__file__).resolve().parent.parent
    templates_dir = package_dir / "templates"

    logger.info("Scanning templates directory", templates_dir=str(templates_dir))

    if not templates_dir.exists():
        logger.warning("Templates directory not found", path=str(templates_dir))
        return {"templates": templates}

    # Scan SMS templates
    sms_dir = templates_dir / "sms"
    if sms_dir.exists():
        for template_file in sorted(sms_dir.iterdir()):
            if template_file.is_file() and template_file.suffix == ".txt":
                templates["sms"].append(
                    {
                        "template_id": template_file.stem,
                        "channel": "SMS",
                        "filename": template_file.name,
                    }
                )

    # Scan email templates (HTML files indicate a template; text is the plain variant)
    email_dir = templates_dir / "email"
    if email_dir.exists():
        seen: set[str] = set()
        for template_file in sorted(email_dir.iterdir()):
            if template_file.is_file() and template_file.stem not in seen:
                seen.add(template_file.stem)
                has_html = (email_dir / f"{template_file.stem}.html").exists()
                has_text = (email_dir / f"{template_file.stem}.txt").exists()
                templates["email"].append(
                    {
                        "template_id": template_file.stem,
                        "channel": "EMAIL",
                        "has_html": has_html,
                        "has_text": has_text,
                    }
                )

    logger.info(
        "Templates listed",
        sms_count=len(templates["sms"]),
        email_count=len(templates["email"]),
    )

    return {"templates": templates}


@router.post("")
async def create_template(response: Response) -> dict:
    """Stub endpoint for creating templates.

    Templates are file-based and managed through deployment, so this
    endpoint is not implemented.

    Args:
        response: The FastAPI response object for setting status codes.

    Returns:
        A dictionary with an error message explaining this is not implemented.
    """
    response.status_code = 501
    return {
        "error": "Not Implemented",
        "detail": "Templates are file-based and managed through deployment. "
        "Use the template files in the templates directory instead.",
    }
