from __future__ import annotations

import argparse
import os
from uuid import uuid4

from sqlalchemy import func, insert, select
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.identity import User


TARGET_ACTIVE_USERS = 1_000_000
BATCH_SIZE = 10_000
REQUIRED_CONFIRMATION = "COMMONDEPTH_ALLOW_SYNTHETIC_USERS"


def _database_host() -> str | None:
    settings = get_settings()
    database_url = getattr(settings, "database_url", None)

    if not database_url:
        database_url = getattr(settings, "DATABASE_URL", None)

    if not database_url:
        raise RuntimeError("Database URL could not be resolved from application settings.")

    return make_url(str(database_url)).host


def _require_safe_environment(*, execute: bool) -> None:
    host = _database_host()

    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(
            "Synthetic user population is restricted to a local database. "
            f"Resolved database host: {host!r}"
        )

    if execute and os.environ.get(REQUIRED_CONFIRMATION) != "1":
        raise RuntimeError(
            f"Set {REQUIRED_CONFIRMATION}=1 explicitly before inserting "
            "synthetic development users."
        )


def _active_user_count(db) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.status == "active")
        )
        or 0
    )


def populate_to_target(target: int) -> tuple[int, int]:
    with SessionLocal() as db:
        current = _active_user_count(db)

        if current > target:
            raise RuntimeError(
                f"Active user count ({current}) already exceeds target ({target}). "
                "No users will be removed."
            )

        remaining = target - current

        if remaining == 0:
            return current, 0

        inserted = 0

        while inserted < remaining:
            batch_size = min(BATCH_SIZE, remaining - inserted)

            rows = [
                {
                    "id": uuid4(),
                    "status": "active",
                }
                for _ in range(batch_size)
            ]

            db.execute(insert(User), rows)
            db.commit()

            inserted += batch_size

            print(
                f"Inserted {inserted:,}/{remaining:,} "
                f"synthetic users; active target progress: "
                f"{current + inserted:,}/{target:,}"
            )

        return current, inserted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate a LOCAL COMMONDEPTH development database with synthetic active users."
    )
    parser.add_argument(
        "--target-active-users",
        type=int,
        default=TARGET_ACTIVE_USERS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    args = parser.parse_args()

    if args.target_active_users < 1:
        raise SystemExit("--target-active-users must be at least 1.")

    _require_safe_environment(execute=not args.dry_run)

    with SessionLocal() as db:
        current = _active_user_count(db)

    remaining = max(args.target_active_users - current, 0)

    print(f"Current active users: {current:,}")
    print(f"Target active users:  {args.target_active_users:,}")
    print(f"Users to add:         {remaining:,}")
    print("Profiles to create:   0")
    print("Follow relationships: 0")
    print("Posts/engagement:     0")

    if args.dry_run:
        print("DRY RUN: no database changes made.")
        return

    if remaining == 0:
        print("Target already satisfied; no database changes made.")
        return

    current, inserted = populate_to_target(args.target_active_users)

    with SessionLocal() as db:
        final_count = _active_user_count(db)

    print()
    print(f"Initial active users: {current:,}")
    print(f"Inserted users:       {inserted:,}")
    print(f"Final active users:   {final_count:,}")


if __name__ == "__main__":
    main()
