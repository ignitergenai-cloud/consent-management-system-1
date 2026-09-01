"""Command handler for internal system commands (pause / resume collection)."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()

# Module-level state for consent-collection pause control
_collection_paused: bool = False
_pause_scope: str | None = None
_pause_reason: str | None = None


class CommandHandler:
    """Handle internal commands that affect consent collection behaviour."""

    @staticmethod
    async def handle_pause(scope: str, reason: str) -> None:
        """Pause consent collection for the given scope.

        Args:
            scope: The scope of the pause (e.g. ``"all"``, a channel name).
            reason: Human-readable reason for pausing.
        """
        global _collection_paused, _pause_scope, _pause_reason  # noqa: PLW0603
        _collection_paused = True
        _pause_scope = scope
        _pause_reason = reason
        logger.warning(
            "consent_collection_paused",
            scope=scope,
            reason=reason,
        )

    @staticmethod
    async def handle_resume() -> None:
        """Resume consent collection."""
        global _collection_paused, _pause_scope, _pause_reason  # noqa: PLW0603
        prev_scope = _pause_scope
        _collection_paused = False
        _pause_scope = None
        _pause_reason = None
        logger.info("consent_collection_resumed", previous_scope=prev_scope)


def is_paused() -> bool:
    """Return whether consent collection is currently paused."""
    return _collection_paused


def get_pause_scope() -> str | None:
    """Return the current pause scope, or ``None`` if not paused."""
    return _pause_scope


def get_pause_reason() -> str | None:
    """Return the current pause reason, or ``None`` if not paused."""
    return _pause_reason
