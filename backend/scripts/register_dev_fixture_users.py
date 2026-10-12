from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.development_fixture import DevelopmentFixtureUser
from app.models.identity import User


FIXTURE_NAME = "million-user-social"
EXPECTED_SYNTHETIC_USERS = 994_692
BATCH_SIZE = 10_000

SYNTHETIC_START = datetime(
    2026,
    10,
    8,
    11,
    26,
    9,
    123622,
    tzinfo=timezone.utc,
)

SYNTHETIC_END = datetime(
    2026,
    10,
    8,
    11,
    29,
    18,
    370807,
    tzinfo=timezone.utc,
)

REQUIRED_CONFIRMATION = "COMMONDEPTH_ALLOW_SYNTHETIC_USERS"


def _database_host() -> str:
    settings = get_settings()
    url = make_url(settings.database_url)
    return url.host or ""


def _validate_environment() -> None:
    settings = get_settings()

    if settings.environment != "development":
        raise RuntimeError(
            "Refusing fixture registration: environment must be 'development'."
        )

    host = _database_host()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(
            "Refusing fixture registration: database host must be local."
        )

    if os.getenv(REQUIRED_CONFIRMATION) != "1":
        raise RuntimeError(
            "Set COMMONDEPTH_ALLOW_SYNTHETIC_USERS=1 to authorize "
            "development fixture registration."
        )


def _candidate_count(db) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.status == "active",
                User.created_at >= SYNTHETIC_START,
                User.created_at <= SYNTHETIC_END,
            )
        )
        or 0
    )


def _existing_registry_count(db) -> int:
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


def _candidate_ids(db):
    return db.scalars(
        select(User.id)
        .where(
            User.status == "active",
            User.created_at >= SYNTHETIC_START,
            User.created_at <= SYNTHETIC_END,
        )
        .order_by(User.created_at.asc(), User.id.asc())
    ).yield_per(BATCH_SIZE)


def main() -> None:
    _validate_environment()

    db = SessionLocal()

    try:
        existing_count = _existing_registry_count(db)

        print(f"Fixture: {FIXTURE_NAME}")
        print(f"Expected synthetic users: {EXPECTED_SYNTHETIC_USERS:,}")
        print(f"Existing registry rows:    {existing_count:,}")

        if existing_count not in {0, EXPECTED_SYNTHETIC_USERS}:
            raise RuntimeError(
                "Refusing fixture registration: existing registry is partially "
                "populated. Reconcile it manually before continuing."
            )

        if existing_count == EXPECTED_SYNTHETIC_USERS:
            print("Fixture registry already complete. No changes made.")
            return

        candidate_count = _candidate_count(db)

        print(f"Candidate synthetic users: {candidate_count:,}")

        if candidate_count != EXPECTED_SYNTHETIC_USERS:
            raise RuntimeError(
                "Refusing fixture registration: synthetic population boundary "
                f"returned {candidate_count:,} users; expected "
                f"{EXPECTED_SYNTHETIC_USERS:,}."
            )

        inserted = 0
        batch: list[dict[str, object]] = []

        for user_id in _candidate_ids(db):
            batch.append(
                {
                    "user_id": user_id,
                    "fixture_name": FIXTURE_NAME,
                }
            )

            if len(batch) >= BATCH_SIZE:
                db.execute(
                    DevelopmentFixtureUser.__table__.insert(),
                    batch,
                )
                inserted += len(batch)
                batch.clear()

                print(
                    f"Registered: {inserted:,}/{EXPECTED_SYNTHETIC_USERS:,}",
                    flush=True,
                )

        if batch:
            db.execute(
                DevelopmentFixtureUser.__table__.insert(),
                batch,
            )
            inserted += len(batch)

        if inserted != EXPECTED_SYNTHETIC_USERS:
            raise RuntimeError(
                "Fixture registration batch count mismatch: "
                f"inserted {inserted:,}; expected "
                f"{EXPECTED_SYNTHETIC_USERS:,}."
            )

        final_count = _existing_registry_count(db)

        if final_count != EXPECTED_SYNTHETIC_USERS:
            raise RuntimeError(
                "Fixture registration verification failed before commit: "
                f"{final_count:,} rows found; expected "
                f"{EXPECTED_SYNTHETIC_USERS:,}."
            )

        db.commit()

        print()
        print("Fixture registration completed successfully.")
        print(f"Registered users: {final_count:,}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
