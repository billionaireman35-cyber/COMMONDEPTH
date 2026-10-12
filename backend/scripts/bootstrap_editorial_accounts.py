from __future__ import annotations

from dataclasses import dataclass
from getpass import getpass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.identity import User, UserIdentity
from app.models.profile import Profile
from app.services.identity_registration import (
    DuplicateIdentityError,
    InvalidRegistrationInputError,
    register_identity,
)
from app.services.profile import (
    ProfileAlreadyExistsError,
    UsernameAlreadyExistsError,
    create_profile,
)
from app.services.profile_verification import verify_profile


EMAIL_DOMAIN = "common.dpdns.org"

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128


@dataclass(frozen=True)
class EditorialAccount:
    username: str
    display_name: str
    biography: str
    location: str | None = None


EDITORIAL_ACCOUNTS = (
    EditorialAccount(
        username="commondepth",
        display_name="COMMONDEPTH",
        biography="The official COMMONDEPTH network. People. Ideas. Voice. Connection.",
    ),
    EditorialAccount(
        username="technology",
        display_name="Technology",
        biography="Technology, innovation, software, devices, infrastructure and the future.",
    ),
    EditorialAccount(
        username="ai",
        display_name="AI",
        biography="Artificial intelligence, research, products, agents, robotics and ideas.",
    ),
    EditorialAccount(
        username="business",
        display_name="Business",
        biography="Business, markets, entrepreneurship, companies and the global economy.",
    ),
    EditorialAccount(
        username="africa",
        display_name="Africa",
        biography="Africa, its people, ideas, culture, innovation, business and future.",
    ),
    EditorialAccount(
        username="travel",
        display_name="Travel",
        biography="Places, journeys, people, cultures and experiences from around the world.",
    ),
    EditorialAccount(
        username="football",
        display_name="Football",
        biography="Football from Africa and around the world.",
    ),
    EditorialAccount(
        username="sports",
        display_name="Sports",
        biography="Sports, athletes, competition, stories and the people behind the game.",
    ),
    EditorialAccount(
        username="culture",
        display_name="Culture",
        biography="Culture, traditions, creativity, communities and the stories that connect us.",
    ),
    EditorialAccount(
        username="photography",
        display_name="Photography",
        biography="Photography, visual storytelling, places, people and perspectives.",
    ),
    EditorialAccount(
        username="design",
        display_name="Design",
        biography="Design, creativity, products, interfaces, architecture and visual ideas.",
    ),
    EditorialAccount(
        username="science",
        display_name="Science",
        biography="Science, discovery, research, exploration and the pursuit of knowledge.",
    ),
    EditorialAccount(
        username="entrepreneurship",
        display_name="Entrepreneurship",
        biography="Entrepreneurship, founders, startups, building and creating what comes next.",
    ),
    EditorialAccount(
        username="ideas",
        display_name="Ideas",
        biography="Ideas, perspectives, questions and conversations worth exploring.",
    ),
    EditorialAccount(
        username="tevgar_ai",
        display_name="Tevqar AI",
        biography="Artificial intelligence, technology, research, products, agents and the future.",
    ),
    EditorialAccount(
        username="vexqar_org",
        display_name="Vexqar.org",
        biography="Technology, ideas, innovation and perspectives from the Vexqar.org community.",
    ),
    EditorialAccount(
        username="goldxtechnologies_org",
        display_name="Goldx Technologies",
        biography="Goldx Technologies — building infrastructure, products and technology for a connected world.",
    ),
)


def _email_for(username: str) -> str:
    return f"{username}@{EMAIL_DOMAIN}"


def _validate_password(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must contain at least {PASSWORD_MIN_LENGTH} characters."
        )

    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must not exceed {PASSWORD_MAX_LENGTH} characters."
        )


def _find_identity(db: Session, email: str) -> UserIdentity | None:
    statement = select(UserIdentity).where(
        UserIdentity.provider == "email",
        UserIdentity.provider_subject == email,
    )
    return db.scalar(statement)


def _find_profile(db: Session, user_id) -> Profile | None:
    statement = select(Profile).where(Profile.user_id == user_id)
    return db.scalar(statement)


def _preflight_editorial_accounts() -> bool:
    print("Preflight: checking editorial accounts before any creation...")
    print()

    valid = True

    with SessionLocal() as db:
        seen_usernames: set[str] = set()
        seen_emails: set[str] = set()

        for account in EDITORIAL_ACCOUNTS:
            email = _email_for(account.username)

            if account.username in seen_usernames:
                print(
                    f"[ERROR] {account.username}: duplicate username "
                    "in bootstrap configuration."
                )
                valid = False

            if email in seen_emails:
                print(
                    f"[ERROR] {account.username}: duplicate email "
                    "in bootstrap configuration."
                )
                valid = False

            seen_usernames.add(account.username)
            seen_emails.add(email)

            identity = _find_identity(db, email)

            username_statement = select(Profile).where(
                Profile.username == account.username
            )
            username_profile = db.scalar(username_statement)

            if identity is None:
                if username_profile is not None:
                    print(
                        f"[ERROR] {account.username}: username is already "
                        "owned by another existing profile."
                    )
                    valid = False
                else:
                    print(
                        f"[PLAN] {account.username}: create identity, "
                        "profile, and verification."
                    )
                continue

            user = db.get(User, identity.user_id)

            if user is None:
                print(
                    f"[ERROR] {account.username}: email identity exists "
                    "but its user does not."
                )
                valid = False
                continue

            user_profile = _find_profile(db, user.id)

            if (
                username_profile is not None
                and username_profile.user_id != user.id
            ):
                print(
                    f"[ERROR] {account.username}: configured username is "
                    "owned by a different user."
                )
                valid = False
                continue

            if (
                user_profile is not None
                and user_profile.username != account.username
            ):
                print(
                    f"[ERROR] {account.username}: existing identity already "
                    f"has profile username '{user_profile.username}'."
                )
                valid = False
                continue

            if user_profile is None:
                print(
                    f"[PLAN] {account.username}: existing identity; "
                    "create missing profile and verify."
                )
            elif user_profile.verified_at is None:
                print(
                    f"[PLAN] {account.username}: existing identity/profile; "
                    "verify profile."
                )
            else:
                print(
                    f"[SKIP] {account.username}: identity and verified "
                    "profile already exist."
                )

    print()

    if not valid:
        print("Preflight failed. No accounts were created or modified.")
        return False

    print("Preflight passed. No database mutations were performed.")
    return True


def bootstrap_editorial_accounts(password: str) -> None:
    _validate_password(password)

    if not _preflight_editorial_accounts():
        raise SystemExit(1)

    print()
    print("Starting editorial account bootstrap...")
    print()

    for account in EDITORIAL_ACCOUNTS:
        email = _email_for(account.username)

        with SessionLocal() as db:
            identity = _find_identity(db, email)

            if identity is not None:
                user = db.get(User, identity.user_id)

                if user is None:
                    print(
                        f"[ERROR] {account.username}: identity exists "
                        "but its user does not."
                    )
                    continue

                print(
                    f"[SKIP] {account.username}: identity already exists."
                )

                profile = _find_profile(db, user.id)

                if profile is None:
                    try:
                        profile = create_profile(
                            db,
                            user_id=user.id,
                            username=account.username,
                            display_name=account.display_name,
                            biography=account.biography,
                            location=account.location,
                            visibility="public",
                        )
                        print(
                            f"[CREATE] {account.username}: profile created."
                        )
                    except (
                        ProfileAlreadyExistsError,
                        UsernameAlreadyExistsError,
                    ):
                        profile = _find_profile(db, user.id)
                        if profile is None:
                            print(
                                f"[ERROR] {account.username}: "
                                "profile creation conflict."
                            )
                            continue
                    except Exception as exc:
                        raise RuntimeError(
                            f"{account.username}: existing-profile creation failed."
                        ) from exc

                if profile is not None and profile.verified_at is None:
                    try:
                        verify_profile(db, user_id=user.id)
                        print(
                            f"[VERIFY] {account.username}: profile verified."
                        )
                    except Exception as exc:
                        raise RuntimeError(
                            f"{account.username}: existing-profile verification failed."
                        ) from exc

                continue

            try:
                result = register_identity(
                    db,
                    email=email,
                    password=password,
                )
            except DuplicateIdentityError:
                print(
                    f"[SKIP] {account.username}: identity was created "
                    "concurrently; no credential changes made."
                )
                continue
            except InvalidRegistrationInputError as exc:
                print(
                    f"[ERROR] {account.username}: registration input "
                    f"rejected: {exc}"
                )
                continue
            except Exception as exc:
                raise RuntimeError(
                    f"{account.username}: registration failed."
                ) from exc

            print(
                f"[CREATE] {account.username}: identity created "
                f"(user {result.user_id})."
            )

            try:
                profile = create_profile(
                    db,
                    user_id=result.user_id,
                    username=account.username,
                    display_name=account.display_name,
                    biography=account.biography,
                    location=account.location,
                    visibility="public",
                )
                print(
                    f"[CREATE] {account.username}: profile created."
                )
            except ProfileAlreadyExistsError:
                profile = _find_profile(db, result.user_id)
            except UsernameAlreadyExistsError as exc:
                print(
                    f"[ERROR] {account.username}: username conflict: {exc}"
                )
                continue
            except Exception as exc:
                raise RuntimeError(
                    f"{account.username}: profile creation failed."
                ) from exc

            if profile is None:
                print(
                    f"[ERROR] {account.username}: profile was not found "
                    "after registration."
                )
                continue

            try:
                verify_profile(db, user_id=result.user_id)
                print(
                    f"[VERIFY] {account.username}: profile verified."
                )
            except Exception as exc:
                raise RuntimeError(
                    f"{account.username}: profile verification failed."
                ) from exc



def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Bootstrap COMMONDEPTH editorial accounts."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Run editorial account preflight without making "
            "database changes."
        ),
    )
    args = parser.parse_args()

    if args.dry_run:
        print("COMMONDEPTH editorial account bootstrap")
        print("---------------------------------------")
        print(f"Authentication email domain: {EMAIL_DOMAIN}")
        print(f"Accounts configured: {len(EDITORIAL_ACCOUNTS)}")
        print()
        print("DRY RUN: no database mutations will be performed.")
        print()
        if not _preflight_editorial_accounts():
            raise SystemExit(1)
        return

    print("COMMONDEPTH editorial account bootstrap")
    print("---------------------------------------")
    print(f"Authentication email domain: {EMAIL_DOMAIN}")
    print(f"Accounts configured: {len(EDITORIAL_ACCOUNTS)}")
    print()
    print("The password will not be displayed, logged, or stored.")
    print("Existing identities will be skipped and their credentials will")
    print("not be changed.")
    print()

    password = getpass("Shared editorial bootstrap password: ")
    confirmation = getpass("Confirm shared editorial bootstrap password: ")

    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    _validate_password(password)
    bootstrap_editorial_accounts(password)


if __name__ == "__main__":
    main()
