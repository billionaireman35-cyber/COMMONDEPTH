from uuid import UUID

from sqlalchemy.orm import Session

from app.integrations.media_storage.protocol import MediaStorage
from app.models.media import MediaAsset
from app.models.profile import Profile
from app.repositories.content import ContentRepository
from app.repositories.media import MediaRepository
from app.schemas.profile import (
    ProfileDiscoveryResponse,
    ProfileResponse,
)


class InvalidProfileMediaError(Exception):
    """Raised when a profile image asset cannot be used."""


def validate_profile_image_asset(
    db: Session,
    *,
    owner_id: UUID,
    asset_id: UUID | None,
) -> MediaAsset | None:
    """Validate ownership and upload completion without changing asset state."""
    if asset_id is None:
        return None

    repository = MediaRepository(db)
    asset = repository.get_asset(asset_id)

    if (
        asset is None
        or asset.owner_id != owner_id
        or asset.media_type != "image"
        or asset.deleted_at is not None
        or asset.status not in {"processing", "ready"}
    ):
        raise InvalidProfileMediaError(
            "Profile image asset is not available."
        )

    upload = repository.get_upload_by_asset_id(asset_id)

    if (
        upload is None
        or upload.status != "completed"
        or upload.completed_at is None
    ):
        raise InvalidProfileMediaError(
            "Profile image asset is not available."
        )

    return asset


def serialize_profile_response(
    db: Session,
    profile: Profile,
    *,
    storage: MediaStorage,
    viewer_user_id: UUID | None,
) -> ProfileResponse:
    """Build a full profile response with fresh signed image URLs."""
    response = ProfileResponse.model_validate(profile)
    response.post_count = ContentRepository(db).count_by_author(
        author_id=profile.user_id,
        viewer_user_id=viewer_user_id,
    )
    repository = MediaRepository(db)

    if profile.avatar_asset_id is not None:
        asset = repository.get_asset(profile.avatar_asset_id)
        if asset is not None:
            response.avatar = storage.get_read_url(
                storage_key=asset.storage_key
            )

    if profile.banner_asset_id is not None:
        asset = repository.get_asset(profile.banner_asset_id)
        if asset is not None:
            response.banner = storage.get_read_url(
                storage_key=asset.storage_key
            )

    return response


def serialize_profile_discovery_response(
    db: Session,
    profile: Profile,
    *,
    storage: MediaStorage,
) -> ProfileDiscoveryResponse:
    """Build a discovery response without exposing asset identifiers."""
    response = ProfileDiscoveryResponse.model_validate(profile)

    if profile.avatar_asset_id is not None:
        asset = MediaRepository(db).get_asset(profile.avatar_asset_id)
        if asset is not None:
            response.avatar = storage.get_read_url(
                storage_key=asset.storage_key
            )

    return response
