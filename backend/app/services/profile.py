import base64
import binascii
import json
import re
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.repositories.profile import ProfileRepository

USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,29}$")

VISIBILITIES = {"public", "private"}

MAX_DISPLAY_NAME_LENGTH = 100
MAX_AVATAR_LENGTH = 2048
MAX_BANNER_LENGTH = 2048
MAX_BIOGRAPHY_LENGTH = 5000
MAX_LOCATION_LENGTH = 160

SEARCH_DEFAULT_LIMIT = 20
SEARCH_MAX_LIMIT = 50
SEARCH_MAX_QUERY_LENGTH = 100


class ProfileError(Exception):
    """Base class for profile service errors."""


class InvalidProfileInputError(ProfileError):
    """Raised when profile input violates the profile contract."""


class ProfileAlreadyExistsError(ProfileError):
    """Raised when the authenticated user already has a profile."""


class UsernameAlreadyExistsError(ProfileError):
    """Raised when a username is already claimed."""


class ProfileNotFoundError(ProfileError):
    """Raised when a requested profile does not exist."""


class InvalidProfileSearchError(ProfileError):
    """Raised when profile search input or cursor is invalid."""


def normalize_username(username: str) -> str:
    if not isinstance(username, str):
        raise InvalidProfileInputError("Invalid username.")

    normalized = username.strip().lower()

    if not USERNAME_PATTERN.fullmatch(normalized):
        raise InvalidProfileInputError(
            "Username must be 3-30 characters, start with a letter, "
            "and contain only letters, numbers, and underscores."
        )

    return normalized


def _validate_optional_text(
    value: str | None,
    *,
    field: str,
    maximum: int,
) -> None:
    if value is not None and len(value) > maximum:
        raise InvalidProfileInputError(
            f"{field} exceeds the maximum length."
        )


def _validate_profile_fields(
    *,
    display_name: str | None,
    avatar: str | None,
    banner: str | None,
    biography: str | None,
    location: str | None,
    visibility: str | None,
) -> None:
    _validate_optional_text(
        display_name,
        field="Display name",
        maximum=MAX_DISPLAY_NAME_LENGTH,
    )
    _validate_optional_text(
        avatar,
        field="Avatar",
        maximum=MAX_AVATAR_LENGTH,
    )
    _validate_optional_text(
        banner,
        field="Banner",
        maximum=MAX_BANNER_LENGTH,
    )
    _validate_optional_text(
        biography,
        field="Biography",
        maximum=MAX_BIOGRAPHY_LENGTH,
    )
    _validate_optional_text(
        location,
        field="Location",
        maximum=MAX_LOCATION_LENGTH,
    )

    if visibility is not None and visibility not in VISIBILITIES:
        raise InvalidProfileInputError("Invalid profile visibility.")


def create_profile(
    db: Session,
    *,
    user_id: UUID,
    username: str,
    display_name: str | None = None,
    avatar: str | None = None,
    banner: str | None = None,
    biography: str | None = None,
    location: str | None = None,
    visibility: str = "public",
) -> Profile:
    normalized_username = normalize_username(username)

    _validate_profile_fields(
        display_name=display_name,
        avatar=avatar,
        banner=banner,
        biography=biography,
        location=location,
        visibility=visibility,
    )

    repository = ProfileRepository(db)

    try:
        if repository.get_by_user_id(user_id) is not None:
            raise ProfileAlreadyExistsError(
                "Profile already exists."
            )

        if repository.get_by_username(normalized_username) is not None:
            raise UsernameAlreadyExistsError(
                "Username already exists."
            )

        profile = Profile(
            user_id=user_id,
            username=normalized_username,
            display_name=display_name,
            avatar=avatar,
            banner=banner,
            biography=biography,
            location=location,
            visibility=visibility,
        )

        repository.add(profile)
        db.flush()
        db.commit()

        return profile

    except (
        ProfileAlreadyExistsError,
        UsernameAlreadyExistsError,
        InvalidProfileInputError,
    ):
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        constraint_name = _integrity_constraint_name(exc)

        if constraint_name == "uq_profiles_user_id":
            raise ProfileAlreadyExistsError(
                "Profile already exists."
            ) from None

        if constraint_name == "uq_profiles_username":
            raise UsernameAlreadyExistsError(
                "Username already exists."
            ) from None

        raise ProfileError(
            "Profile could not be created."
        ) from None
    except Exception:
        db.rollback()
        raise ProfileError(
            "Profile could not be created."
        ) from None


def get_my_profile(
    db: Session,
    *,
    user_id: UUID,
) -> Profile:
    profile = ProfileRepository(db).get_by_user_id(user_id)

    if profile is None:
        raise ProfileNotFoundError("Profile not found.")

    return profile


_UNSET = object()


def _integrity_constraint_name(exc: IntegrityError) -> str | None:
    original = getattr(exc, "orig", None)
    diagnostic = getattr(original, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _is_username_unique_violation(exc: IntegrityError) -> bool:
    return _integrity_constraint_name(exc) == "uq_profiles_username"


def update_profile(
    db: Session,
    *,
    user_id: UUID,
    username: str | None | object = _UNSET,
    display_name: str | None | object = _UNSET,
    avatar: str | None | object = _UNSET,
    banner: str | None | object = _UNSET,
    biography: str | None | object = _UNSET,
    location: str | None | object = _UNSET,
    visibility: str | None | object = _UNSET,
) -> Profile:
    repository = ProfileRepository(db)
    profile = repository.get_by_user_id(user_id)

    if profile is None:
        raise ProfileNotFoundError("Profile not found.")

    normalized_username = None
    if username is not _UNSET:
        if username is None:
            raise InvalidProfileInputError("Invalid username.")
        normalized_username = normalize_username(username)

    def optional_value(value: str | None | object) -> str | None:
        return None if value is _UNSET else value

    _validate_profile_fields(
        display_name=optional_value(display_name),
        avatar=optional_value(avatar),
        banner=optional_value(banner),
        biography=optional_value(biography),
        location=optional_value(location),
        visibility=optional_value(visibility),
    )

    try:
        if (
            normalized_username is not None
            and normalized_username != profile.username
        ):
            existing = repository.get_by_username(normalized_username)

            if existing is not None and existing.id != profile.id:
                raise UsernameAlreadyExistsError(
                    "Username already exists."
                )

            profile.username = normalized_username

        if display_name is not _UNSET:
            profile.display_name = display_name
        if avatar is not _UNSET:
            profile.avatar = avatar
        if banner is not _UNSET:
            profile.banner = banner
        if biography is not _UNSET:
            profile.biography = biography
        if location is not _UNSET:
            profile.location = location
        if visibility is not _UNSET:
            profile.visibility = visibility

        db.flush()
        db.commit()
        return profile

    except UsernameAlreadyExistsError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if _is_username_unique_violation(exc):
            raise UsernameAlreadyExistsError(
                "Username already exists."
            ) from None
        raise ProfileError(
            "Profile could not be updated."
        ) from None
    except Exception:
        db.rollback()
        raise ProfileError(
            "Profile could not be updated."
        ) from None

def get_profile_by_username(
    db: Session,
    *,
    username: str,
    viewer_user_id: UUID | None = None,
) -> Profile:
    normalized_username = normalize_username(username)
    profile = ProfileRepository(db).get_by_username(normalized_username)

    if profile is None:
        raise ProfileNotFoundError("Profile not found.")

    if profile.visibility == "private" and profile.user_id != viewer_user_id:
        raise ProfileNotFoundError("Profile not found.")

    return profile

def _encode_profile_search_cursor(
    *,
    username: str,
    profile_id: UUID,
) -> str:
    payload = {
        "username": username,
        "id": str(profile_id),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).decode("ascii")
    return encoded.rstrip("=")


def _decode_profile_search_cursor(
    cursor: str,
) -> tuple[str, UUID]:
    if not cursor:
        raise InvalidProfileSearchError("Invalid search cursor.")

    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(
            (cursor + padding).encode("ascii")
        )
        payload = json.loads(decoded.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError

        username = payload.get("username")
        profile_id = payload.get("id")

        if not isinstance(username, str):
            raise ValueError

        normalized_username = normalize_username(username)
        parsed_profile_id = UUID(profile_id)

        return normalized_username, parsed_profile_id
    except (
        binascii.Error,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        raise InvalidProfileSearchError(
            "Invalid search cursor."
        ) from None


def search_profiles(
    db: Session,
    *,
    query: str,
    viewer_user_id: UUID,
    limit: int = SEARCH_DEFAULT_LIMIT,
    cursor: str | None = None,
) -> tuple[list[Profile], str | None]:
    if not isinstance(query, str):
        raise InvalidProfileSearchError("Invalid search query.")

    normalized_query = query.strip()

    if not normalized_query:
        raise InvalidProfileSearchError("Search query cannot be empty.")

    if len(normalized_query) > SEARCH_MAX_QUERY_LENGTH:
        raise InvalidProfileSearchError(
            "Search query exceeds the maximum length."
        )

    if limit < 1 or limit > SEARCH_MAX_LIMIT:
        raise InvalidProfileSearchError("Invalid search limit.")

    cursor_username = None
    cursor_profile_id = None

    if cursor is not None:
        (
            cursor_username,
            cursor_profile_id,
        ) = _decode_profile_search_cursor(cursor)

    repository = ProfileRepository(db)

    profiles = repository.search_public_profiles(
        query=normalized_query,
        viewer_user_id=viewer_user_id,
        limit=limit + 1,
        cursor_username=cursor_username,
        cursor_profile_id=cursor_profile_id,
    )

    next_cursor = None

    if len(profiles) > limit:
        profiles = profiles[:limit]
        last_profile = profiles[-1]
        next_cursor = _encode_profile_search_cursor(
            username=last_profile.username,
            profile_id=last_profile.id,
        )

    return profiles, next_cursor
