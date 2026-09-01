"""Bidirectional event transformer between CMS and MIMS formats."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Severity / priority mapping tables
# ---------------------------------------------------------------------------

SEVERITY_TO_PRIORITY: dict[str, str] = {
    "LOW": "P4",
    "MEDIUM": "P3",
    "HIGH": "P2",
    "CRITICAL": "P1",
}

PRIORITY_TO_SEVERITY: dict[str, str] = {v: k for k, v in SEVERITY_TO_PRIORITY.items()}

# ---------------------------------------------------------------------------
# MIMS command type -> CMS event type mapping
# ---------------------------------------------------------------------------

_COMMAND_TYPE_TO_EVENT: dict[str, str] = {
    "PAUSE": "PauseConsentCollection",
    "RESUME": "ResumeConsentCollection",
}


class EventTransformer:
    """Transforms events between internal CMS format and external MIMS format.

    Handles two conversion directions:

    * **CMS -> MIMS** — :meth:`cms_to_mims` converts an ``IncidentDetected``
      (or similar) CMS event into a flat dictionary suitable for MIMS.
    * **MIMS -> CMS** — :meth:`mims_to_cms_command` converts an inbound MIMS
      command (``PAUSE`` / ``RESUME``) into a CMS command payload.
    """

    # ------------------------------------------------------------------
    # CMS -> MIMS
    # ------------------------------------------------------------------

    def cms_to_mims(self, cms_event: dict[str, Any]) -> dict[str, Any]:
        """Transform an internal CMS incident event into MIMS format.

        Args:
            cms_event: A CMS ``EventEnvelope``-style dictionary with at least
                ``event_type``, ``payload``, ``timestamp``, and optionally
                ``correlation_id``.

        Returns:
            A flat dictionary matching the :class:`MIMSIncident` schema.
        """
        payload: dict[str, Any] = cms_event.get("payload", {})
        severity: str = payload.get("severity", "LOW")
        priority = SEVERITY_TO_PRIORITY.get(severity.upper(), "P4")

        detected_at = cms_event.get("timestamp", datetime.now(timezone.utc).isoformat())

        mims_event: dict[str, Any] = {
            "source_system": "consent-management-system",
            "incident_id": payload.get("incident_id", ""),
            "priority": priority,
            "category": payload.get("category", "consent"),
            "subcategory": payload.get("subcategory", ""),
            "title": payload.get("title", ""),
            "description": payload.get("description", ""),
            "affected_users": payload.get("affected_users", 0),
            "detected_at": str(detected_at),
            "metrics": payload.get("metrics", {}),
            "recommended_action": payload.get("recommended_action", ""),
            "correlation_id": cms_event.get("correlation_id", ""),
        }

        logger.debug(
            "cms_to_mims_transformed",
            incident_id=mims_event["incident_id"],
            priority=priority,
        )
        return mims_event

    # ------------------------------------------------------------------
    # MIMS -> CMS
    # ------------------------------------------------------------------

    def mims_to_cms_command(self, mims_command: dict[str, Any]) -> dict[str, Any]:
        """Transform an inbound MIMS command into a CMS command payload.

        Args:
            mims_command: Dictionary with at least ``command_type`` and
                ``incident_id``.

        Returns:
            A payload dictionary suitable for inclusion in a CMS
            ``EventEnvelope``.
        """
        cms_payload: dict[str, Any] = {
            "incident_id": mims_command.get("incident_id", ""),
            "scope": mims_command.get("scope", "all"),
            "reason": mims_command.get("reason", ""),
        }

        command_type = mims_command.get("command_type", "")
        if command_type == "RESUME":
            cms_payload["resume_condition"] = mims_command.get("resume_condition", "")

        logger.debug(
            "mims_to_cms_command_transformed",
            command_type=command_type,
            incident_id=cms_payload["incident_id"],
        )
        return cms_payload

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    @staticmethod
    def get_cms_event_type(mims_command: dict[str, Any]) -> str:
        """Map a MIMS command type to the corresponding CMS event type.

        Args:
            mims_command: Dictionary containing at least ``command_type``.

        Returns:
            The CMS event type string, or ``"UnknownCommand"`` if the
            command type is not recognised.
        """
        command_type = mims_command.get("command_type", "")
        event_type = _COMMAND_TYPE_TO_EVENT.get(command_type, "UnknownCommand")
        if event_type == "UnknownCommand":
            logger.warning(
                "unknown_mims_command_type",
                command_type=command_type,
            )
        return event_type
