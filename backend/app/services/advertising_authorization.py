"""Fail-closed authorization helpers for platform advertising reviewers."""

from uuid import UUID

from app.core.config import get_settings


def configured_advertising_reviewer_ids() -> frozenset[UUID]:
    """Return configured reviewer UUIDs; invalid configuration fails closed."""
    raw = get_settings().advertising_reviewer_user_ids.strip()

    if not raw:
        return frozenset()

    tokens = [item.strip() for item in raw.split(",")]

    if any(not item for item in tokens):
        return frozenset()

    try:
        return frozenset(UUID(item) for item in tokens)
    except (ValueError, AttributeError, TypeError):
        # Never partially accept a malformed reviewer allowlist.
        return frozenset()


def is_configured_advertising_reviewer(user_id: UUID) -> bool:
    """Check the explicit allowlist, not Space membership or ownership."""
    return user_id in configured_advertising_reviewer_ids()
