"""Transactional operations for the global username registry."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.username_registry import UsernameRegistry


USERNAME_RESERVATION_DAYS = 30


class UsernameRegistryError(Exception):
    """Base class for username registry failures."""


class UsernameUnavailableError(UsernameRegistryError):
    """Raised when a username is claimed or reserved."""


class UsernameRegistryInvariantError(UsernameRegistryError):
    """Raised when registry ownership does not match expectations."""


def claim_profile_username(
    db: Session,
    *,
    username: str,
    profile_id: UUID,
    now: datetime | None = None,
) -> UsernameRegistry:
    """Claim a username for a profile within the caller's transaction.

    Database uniqueness constraints remain the final protection against
    simultaneous attempts to claim a previously unregistered username.
    This function deliberately does not commit or roll back.
    """
    current_time = now or datetime.now(timezone.utc)

    statement = (
        select(UsernameRegistry)
        .where(UsernameRegistry.username == username)
        .with_for_update()
    )
    entry = db.scalar(statement)

    if entry is None:
        entry = UsernameRegistry(
            username=username,
            status="claimed",
            owner_type="profile",
            profile_id=profile_id,
        )
        db.add(entry)
        db.flush()
        return entry

    if (
        entry.status == "claimed"
        and entry.owner_type == "profile"
        and entry.profile_id == profile_id
    ):
        return entry

    if (
        entry.status == "reserved"
        and entry.expires_at is not None
        and entry.expires_at <= current_time
    ):
        entry.status = "claimed"
        entry.owner_type = "profile"
        entry.profile_id = profile_id
        entry.space_id = None
        entry.reserved_at = None
        entry.expires_at = None
        db.flush()
        return entry

    raise UsernameUnavailableError("Username already exists.")


def reserve_profile_username(
    db: Session,
    *,
    username: str,
    profile_id: UUID,
    now: datetime | None = None,
) -> UsernameRegistry:
    """Reserve a profile's released username for 30 days.

    The former owner receives no special reclaim privilege during the
    reservation period. The caller must commit or roll back the enclosing
    transaction, including any corresponding Profile changes.
    """
    current_time = now or datetime.now(timezone.utc)

    statement = (
        select(UsernameRegistry)
        .where(UsernameRegistry.username == username)
        .with_for_update()
    )
    entry = db.scalar(statement)

    if (
        entry is None
        or entry.status != "claimed"
        or entry.owner_type != "profile"
        or entry.profile_id != profile_id
    ):
        raise UsernameRegistryInvariantError(
            "Profile username registry ownership is inconsistent."
        )

    entry.status = "reserved"
    entry.owner_type = None
    entry.profile_id = None
    entry.space_id = None
    entry.reserved_at = current_time
    entry.expires_at = current_time + timedelta(
        days=USERNAME_RESERVATION_DAYS
    )

    db.flush()
    return entry
