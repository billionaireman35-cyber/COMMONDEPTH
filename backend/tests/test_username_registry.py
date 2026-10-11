from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.identity import User
from app.models.profile import Profile
from app.models.username_registry import UsernameRegistry
from app.services.username_registry import (
    UsernameRegistryInvariantError,
    UsernameUnavailableError,
    claim_profile_username,
    reserve_profile_username,
)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def make_profile(db, username: str) -> Profile:
    user = User(status="active")
    db.add(user)
    db.flush()

    profile = Profile(user_id=user.id, username=username)
    db.add(profile)
    db.flush()
    return profile


def test_claim_available_username(db):
    profile = make_profile(db, "registry_one")

    entry = claim_profile_username(
        db, username=profile.username, profile_id=profile.id
    )

    assert entry.status == "claimed"
    assert entry.owner_type == "profile"
    assert entry.profile_id == profile.id
    assert entry.space_id is None
    assert entry.reserved_at is None
    assert entry.expires_at is None


def test_same_profile_can_repeat_its_claim(db):
    profile = make_profile(db, "registry_two")

    first = claim_profile_username(
        db, username=profile.username, profile_id=profile.id
    )
    second = claim_profile_username(
        db, username=profile.username, profile_id=profile.id
    )

    assert first.id == second.id


def test_another_profile_cannot_claim_claimed_username(db):
    owner = make_profile(db, "registry_three")
    other = make_profile(db, "registry_four")

    claim_profile_username(
        db, username=owner.username, profile_id=owner.id
    )

    with pytest.raises(UsernameUnavailableError):
        claim_profile_username(
            db, username=owner.username, profile_id=other.id
        )


def test_reserved_username_cannot_be_reclaimed_by_previous_owner(db):
    profile = make_profile(db, "registry_five")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    claim_profile_username(
        db, username=profile.username, profile_id=profile.id, now=now
    )
    reserve_profile_username(
        db, username=profile.username, profile_id=profile.id, now=now
    )

    entry = db.query(UsernameRegistry).filter_by(
        username=profile.username
    ).one()

    assert entry.status == "reserved"
    assert entry.owner_type is None
    assert entry.profile_id is None
    assert entry.reserved_at == now
    assert entry.expires_at == now + timedelta(days=30)

    with pytest.raises(UsernameUnavailableError):
        claim_profile_username(
            db,
            username=profile.username,
            profile_id=profile.id,
            now=now + timedelta(days=29),
        )


def test_expired_reservation_can_be_claimed(db):
    previous_owner = make_profile(db, "registry_six")
    new_owner = make_profile(db, "registry_seven")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    claim_profile_username(
        db,
        username=previous_owner.username,
        profile_id=previous_owner.id,
        now=now,
    )
    reserve_profile_username(
        db,
        username=previous_owner.username,
        profile_id=previous_owner.id,
        now=now,
    )

    entry = claim_profile_username(
        db,
        username=previous_owner.username,
        profile_id=new_owner.id,
        now=now + timedelta(days=30),
    )

    assert entry.status == "claimed"
    assert entry.owner_type == "profile"
    assert entry.profile_id == new_owner.id
    assert entry.reserved_at is None
    assert entry.expires_at is None


def test_reservation_rejects_wrong_owner(db):
    owner = make_profile(db, "registry_eight")
    other = make_profile(db, "registry_nine")

    claim_profile_username(
        db, username=owner.username, profile_id=owner.id
    )

    with pytest.raises(UsernameRegistryInvariantError):
        reserve_profile_username(
            db, username=owner.username, profile_id=other.id
        )

def test_database_rejects_duplicate_registry_username(db):
    owner = make_profile(db, "registry_ten")
    other = make_profile(db, "registry_eleven")

    db.add(
        UsernameRegistry(
            username="registry_shared",
            status="claimed",
            owner_type="profile",
            profile_id=owner.id,
        )
    )
    db.flush()

    db.add(
        UsernameRegistry(
            username="registry_shared",
            status="claimed",
            owner_type="profile",
            profile_id=other.id,
        )
    )

    with pytest.raises(IntegrityError):
        db.flush()

    db.rollback()
