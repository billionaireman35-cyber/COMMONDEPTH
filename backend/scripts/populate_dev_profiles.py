from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.development_fixture import DevelopmentFixtureUser
from app.models.profile import Profile
from app.models.identity import User
from scripts.prototype_dev_profile_identities import (
    FIRST_NAMES,
    LAST_NAMES,
    SEED,
    make_avatar_url,
    make_username,
)
import random


FIXTURE_NAME = "million-user-social"
EXPECTED_SYNTHETIC_USERS = 994_692
BATCH_SIZE = 10_000
REQUIRED_CONFIRMATION = "COMMONDEPTH_ALLOW_SYNTHETIC_USERS"


def _database_host() -> str:
    settings = get_settings()
    url = make_url(settings.database_url)
    return url.host or ""


def _validate_environment() -> None:
    settings = get_settings()

    if settings.environment != "development":
        raise RuntimeError(
            "Refusing synthetic profile population: "
            "environment must be 'development'."
        )

    if _database_host() not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(
            "Refusing synthetic profile population: "
            "database host must be local."
        )

    if os.getenv(REQUIRED_CONFIRMATION) != "1":
        raise RuntimeError(
            "Set COMMONDEPTH_ALLOW_SYNTHETIC_USERS=1 to authorize "
            "synthetic profile population."
        )


def _fixture_user_ids(db) -> list:
    return list(
        db.scalars(
            select(DevelopmentFixtureUser.user_id)
            .where(
                DevelopmentFixtureUser.fixture_name == FIXTURE_NAME,
            )
            .order_by(DevelopmentFixtureUser.created_at.asc())
        )
    )


def _fixture_user_count(db) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(DevelopmentFixtureUser)
            .where(
                DevelopmentFixtureUser.fixture_name == FIXTURE_NAME,
            )
        )
        or 0
    )


def _fixture_profile_count(db) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Profile)
            .join(
                DevelopmentFixtureUser,
                DevelopmentFixtureUser.user_id == Profile.user_id,
            )
            .where(
                DevelopmentFixtureUser.fixture_name == FIXTURE_NAME,
            )
        )
        or 0
    )


def _existing_profile_count(db) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Profile)
        )
        or 0
    )


def _existing_usernames(db) -> set[str]:
    return {
        username.lower()
        for username in db.scalars(
            select(Profile.username)
        ).all()
    }


def _generate_profiles(
    fixture_user_ids: list,
    existing_usernames: set[str],
) -> list[dict[str, object]]:
    rng = random.Random(SEED)
    used = set(existing_usernames)
    generated: list[dict[str, object]] = []

    for user_id in fixture_user_ids:
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        username = make_username(rng, first, last, used)
        display_name = f"{first.capitalize()} {last.capitalize()}"
        avatar = make_avatar_url(username, display_name)

        generated.append(
            {
                "id": None,
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "avatar": avatar,
                "visibility": "public",
            }
        )

    return generated


def _validate_generated_profiles(
    generated: list[dict[str, object]],
    fixture_user_ids: list,
) -> None:
    if len(generated) != EXPECTED_SYNTHETIC_USERS:
        raise RuntimeError(
            f"Generated {len(generated):,} profiles; expected "
            f"{EXPECTED_SYNTHETIC_USERS:,}."
        )

    if len(fixture_user_ids) != EXPECTED_SYNTHETIC_USERS:
        raise RuntimeError(
            f"Fixture contains {len(fixture_user_ids):,} users; expected "
            f"{EXPECTED_SYNTHETIC_USERS:,}."
        )

    user_ids = [item["user_id"] for item in generated]
    usernames = [item["username"] for item in generated]

    if len(user_ids) != len(set(user_ids)):
        raise RuntimeError("Generated duplicate fixture user IDs.")

    if len(usernames) != len(set(usernames)):
        raise RuntimeError("Generated duplicate usernames.")

    for item in generated:
        username = item["username"]
        display_name = item["display_name"]
        avatar = item["avatar"]

        if not isinstance(username, str):
            raise RuntimeError("Generated username is not a string.")

        if not 2 <= len(username) <= 30:
            raise RuntimeError(
                f"Invalid username length: {username!r}"
            )

        if not username[0].isalpha():
            raise RuntimeError(
                f"Invalid username start: {username!r}"
            )

        if not all(
            character.islower()
            or character.isdigit()
            or character == "_"
            for character in username
        ):
            raise RuntimeError(
                f"Invalid username characters: {username!r}"
            )

        if not isinstance(display_name, str) or not 1 <= len(display_name) <= 100:
            raise RuntimeError(
                f"Invalid display name: {display_name!r}"
            )

        if not isinstance(avatar, str) or len(avatar) > 2048:
            raise RuntimeError(
                f"Invalid avatar URL for {username!r}"
            )


def _preflight(db) -> None:
    fixture_count = _fixture_user_count(db)
    fixture_profile_count = _fixture_profile_count(db)
    total_profile_count = _existing_profile_count(db)
    existing_usernames = _existing_usernames(db)

    print(f"Environment:              {get_settings().environment}")
    print(f"Database host:            {_database_host()}")
    print(f"Fixture:                  {FIXTURE_NAME}")
    print(f"Expected fixture users:   {EXPECTED_SYNTHETIC_USERS:,}")
    print(f"Registered fixture users: {fixture_count:,}")
    print(f"Existing fixture profiles:{fixture_profile_count:,}")
    print(f"Total profiles:           {total_profile_count:,}")
    print(f"Existing usernames:       {len(existing_usernames):,}")

    if fixture_count != EXPECTED_SYNTHETIC_USERS:
        raise RuntimeError(
            "Preflight failed: fixture registry count does not match "
            f"{EXPECTED_SYNTHETIC_USERS:,}."
        )

    if fixture_profile_count not in {0, EXPECTED_SYNTHETIC_USERS}:
        raise RuntimeError(
            "Preflight failed: fixture profiles are partially populated."
        )

    if fixture_profile_count == EXPECTED_SYNTHETIC_USERS:
        print("Profiles already complete. No changes required.")
        print("Database changes made: 0")
        return

    fixture_user_ids = _fixture_user_ids(db)
    generated = _generate_profiles(
        fixture_user_ids,
        existing_usernames,
    )

    _validate_generated_profiles(
        generated,
        fixture_user_ids,
    )

    generated_usernames = {
        str(item["username"]).lower()
        for item in generated
    }

    collisions = generated_usernames.intersection(existing_usernames)

    if collisions:
        raise RuntimeError(
            f"Preflight failed: {len(collisions):,} generated usernames "
            "already exist."
        )

    print(f"Profiles to create:      {len(generated):,}")
    print(f"Username collisions:     {len(collisions):,}")
    print("Visibility:              public")
    print("Verified profiles:       0")
    print("Avatar strategy:         deterministic DiceBear initials")
    print("Database changes made:   0")
    print("PREFLIGHT: PASS")


def _apply(db) -> None:
    fixture_count = _fixture_user_count(db)
    fixture_profile_count = _fixture_profile_count(db)

    if fixture_count != EXPECTED_SYNTHETIC_USERS:
        raise RuntimeError(
            "Refusing profile population: fixture registry is incomplete."
        )

    if fixture_profile_count not in {0, EXPECTED_SYNTHETIC_USERS}:
        raise RuntimeError(
            "Refusing profile population: fixture profiles are partially "
            "populated."
        )

    if fixture_profile_count == EXPECTED_SYNTHETIC_USERS:
        print("Profiles already complete. No changes made.")
        return

    fixture_user_ids = _fixture_user_ids(db)
    existing_usernames = _existing_usernames(db)

    generated = _generate_profiles(
        fixture_user_ids,
        existing_usernames,
    )

    _validate_generated_profiles(
        generated,
        fixture_user_ids,
    )

    rows: list[dict[str, object]] = []

    for item in generated:
        rows.append(
            {
                "user_id": item["user_id"],
                "username": item["username"],
                "display_name": item["display_name"],
                "avatar": item["avatar"],
                "banner": None,
                "biography": None,
                "location": None,
                "visibility": "public",
                "verified_at": None,
            }
        )

        if len(rows) >= BATCH_SIZE:
            db.execute(
                insert(Profile),
                rows,
            )
            rows.clear()

    if rows:
        db.execute(
            insert(Profile),
            rows,
        )

    final_count = _fixture_profile_count(db)

    if final_count != EXPECTED_SYNTHETIC_USERS:
        raise RuntimeError(
            "Profile population verification failed before commit: "
            f"{final_count:,} fixture profiles found; expected "
            f"{EXPECTED_SYNTHETIC_USERS:,}."
        )

    db.commit()

    print("Synthetic profile population completed successfully.")
    print(f"Profiles created: {final_count:,}")
    print("Database changes made:", final_count)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Validate the fixture and generated profiles without writing.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create the synthetic profiles.",
    )
    args = parser.parse_args()

    if args.preflight == args.apply:
        raise SystemExit(
            "Specify exactly one of --preflight or --apply."
        )

    _validate_environment()

    db = SessionLocal()

    try:
        if args.preflight:
            _preflight(db)
        else:
            _apply(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
