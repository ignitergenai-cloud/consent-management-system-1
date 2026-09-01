"""Tests for :class:`EventTransformer`."""

from __future__ import annotations

from typing import Any

import pytest

from incident_bridge.services.event_transformer import (
    SEVERITY_TO_PRIORITY,
    EventTransformer,
)


# ---------------------------------------------------------------------------
# cms_to_mims
# ---------------------------------------------------------------------------


class TestCmsToMims:
    """Tests for :meth:`EventTransformer.cms_to_mims`."""

    def test_transforms_incident_detected_to_mims_format(
        self,
        event_transformer: EventTransformer,
        sample_cms_incident_event: dict[str, Any],
    ) -> None:
        """A well-formed IncidentDetected event is correctly mapped."""
        result = event_transformer.cms_to_mims(sample_cms_incident_event)

        assert result["source_system"] == "consent-management-system"
        assert result["incident_id"] == "INC-1001"
        assert result["priority"] == "P2"  # HIGH -> P2
        assert result["category"] == "consent"
        assert result["subcategory"] == "data-breach"
        assert result["title"] == "Potential data breach detected"
        assert result["description"] == "Unusual access patterns found"
        assert result["affected_users"] == 150
        assert result["detected_at"] == "2026-01-15T12:00:00Z"
        assert result["metrics"] == {"error_rate": 0.05}
        assert result["recommended_action"] == "Investigate access logs"
        assert result["correlation_id"] == "corr-001"

    def test_defaults_for_missing_payload_fields(
        self, event_transformer: EventTransformer
    ) -> None:
        """Missing payload fields fall back to sensible defaults."""
        minimal_event: dict[str, Any] = {
            "event_type": "IncidentDetected",
            "payload": {"incident_id": "INC-9999"},
        }
        result = event_transformer.cms_to_mims(minimal_event)

        assert result["incident_id"] == "INC-9999"
        assert result["priority"] == "P4"  # default severity LOW -> P4
        assert result["affected_users"] == 0
        assert result["metrics"] == {}
        assert result["recommended_action"] == ""
        assert result["source_system"] == "consent-management-system"


# ---------------------------------------------------------------------------
# Severity -> Priority mapping
# ---------------------------------------------------------------------------


class TestSeverityToPriority:
    """Tests for the SEVERITY_TO_PRIORITY mapping."""

    @pytest.mark.parametrize(
        ("severity", "expected_priority"),
        [
            ("LOW", "P4"),
            ("MEDIUM", "P3"),
            ("HIGH", "P2"),
            ("CRITICAL", "P1"),
        ],
    )
    def test_all_severity_levels_map_correctly(
        self,
        event_transformer: EventTransformer,
        severity: str,
        expected_priority: str,
    ) -> None:
        """Each CMS severity maps to the expected MIMS priority."""
        event: dict[str, Any] = {
            "event_type": "IncidentDetected",
            "timestamp": "2026-06-01T00:00:00Z",
            "payload": {
                "incident_id": f"INC-{severity}",
                "severity": severity,
            },
        }
        result = event_transformer.cms_to_mims(event)
        assert result["priority"] == expected_priority

    def test_unknown_severity_defaults_to_p4(
        self, event_transformer: EventTransformer
    ) -> None:
        """An unrecognised severity string defaults to P4."""
        event: dict[str, Any] = {
            "event_type": "IncidentDetected",
            "payload": {
                "incident_id": "INC-UNK",
                "severity": "UNKNOWN",
            },
        }
        result = event_transformer.cms_to_mims(event)
        assert result["priority"] == "P4"

    def test_mapping_dict_has_four_entries(self) -> None:
        """The static mapping contains exactly the four expected entries."""
        assert len(SEVERITY_TO_PRIORITY) == 4
        assert set(SEVERITY_TO_PRIORITY.keys()) == {
            "LOW",
            "MEDIUM",
            "HIGH",
            "CRITICAL",
        }


# ---------------------------------------------------------------------------
# mims_to_cms_command
# ---------------------------------------------------------------------------


class TestMimsToCmsCommand:
    """Tests for :meth:`EventTransformer.mims_to_cms_command`."""

    def test_pause_command_is_transformed(
        self,
        event_transformer: EventTransformer,
        sample_mims_pause_command: dict[str, Any],
    ) -> None:
        """A PAUSE command produces a valid CMS payload."""
        result = event_transformer.mims_to_cms_command(sample_mims_pause_command)

        assert result["incident_id"] == "INC-1001"
        assert result["scope"] == "all"
        assert result["reason"] == "Active incident investigation"
        # PAUSE commands should NOT include resume_condition
        assert "resume_condition" not in result

    def test_resume_command_includes_resume_condition(
        self,
        event_transformer: EventTransformer,
        sample_mims_resume_command: dict[str, Any],
    ) -> None:
        """A RESUME command includes the resume_condition field."""
        result = event_transformer.mims_to_cms_command(sample_mims_resume_command)

        assert result["incident_id"] == "INC-1001"
        assert result["scope"] == "all"
        assert result["reason"] == "Incident resolved"
        assert result["resume_condition"] == "All clear from security team"

    def test_unknown_command_type_still_transforms(
        self, event_transformer: EventTransformer
    ) -> None:
        """An unknown command type is still transformed to a CMS payload."""
        unknown_cmd: dict[str, Any] = {
            "command_type": "ESCALATE",
            "incident_id": "INC-5555",
            "scope": "region-eu",
            "reason": "Needs escalation",
        }
        result = event_transformer.mims_to_cms_command(unknown_cmd)

        assert result["incident_id"] == "INC-5555"
        assert result["scope"] == "region-eu"
        assert result["reason"] == "Needs escalation"


# ---------------------------------------------------------------------------
# get_cms_event_type
# ---------------------------------------------------------------------------


class TestGetCmsEventType:
    """Tests for :meth:`EventTransformer.get_cms_event_type`."""

    def test_pause_maps_to_pause_consent_collection(
        self, event_transformer: EventTransformer
    ) -> None:
        assert (
            event_transformer.get_cms_event_type({"command_type": "PAUSE"})
            == "PauseConsentCollection"
        )

    def test_resume_maps_to_resume_consent_collection(
        self, event_transformer: EventTransformer
    ) -> None:
        assert (
            event_transformer.get_cms_event_type({"command_type": "RESUME"})
            == "ResumeConsentCollection"
        )

    def test_unknown_returns_unknown_command(
        self, event_transformer: EventTransformer
    ) -> None:
        assert (
            event_transformer.get_cms_event_type({"command_type": "REBOOT"})
            == "UnknownCommand"
        )

    def test_missing_command_type_returns_unknown_command(
        self, event_transformer: EventTransformer
    ) -> None:
        assert event_transformer.get_cms_event_type({}) == "UnknownCommand"
