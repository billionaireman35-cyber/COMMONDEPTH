from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.integrations.media_storage import MediaStorage, UploadAllocation
from app.models.media import MediaAsset, MediaUpload
from app.repositories.media import MediaRepository


class MediaError(Exception):
    """Base error for Media domain operations."""


class MediaValidationError(MediaError):
    """Raised when media metadata is invalid."""


class MediaStorageError(MediaError):
    """Raised when storage allocation or inspection fails."""


@dataclass(frozen=True)
class MediaUploadResult:
    asset: MediaAsset
    upload: MediaUpload
    allocation: UploadAllocation


_UPLOAD_EXPIRY = timedelta(minutes=30)

_MAX_FILE_SIZE = {
    "image": 10 * 1024 * 1024,
    "video": 200 * 1024 * 1024,
    "audio": 25 * 1024 * 1024,
}

_ALLOWED_MIME_TYPES = {
    "image": {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    },
    "video": {
        "video/mp4",
        "video/webm",
        "video/quicktime",
    },
    "audio": {
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
    },
}


def _validate_metadata(
    *,
    media_type: str,
    mime_type: str,
    file_size: int,
) -> None:
    if media_type not in _MAX_FILE_SIZE:
        raise MediaValidationError("Unsupported media type.")

    if mime_type not in _ALLOWED_MIME_TYPES[media_type]:
        raise MediaValidationError("Unsupported MIME type for media type.")

    if file_size <= 0:
        raise MediaValidationError("File size must be greater than zero.")

    if file_size > _MAX_FILE_SIZE[media_type]:
        raise MediaValidationError("File exceeds the maximum allowed size.")


def _build_storage_key(
    *,
    user_id: UUID,
    media_type: str,
) -> str:
    return f"media/{user_id}/{media_type}/{uuid4()}"


def create_media_upload(
    db: Session,
    *,
    storage: MediaStorage,
    owner_id: UUID,
    media_type: str,
    mime_type: str,
    file_size: int,
) -> MediaUploadResult:
    """
    Allocate storage for a new media upload.

    The database records remain in the pending state until the stored
    object is independently inspected and the media lifecycle advances.
    """
    _validate_metadata(
        media_type=media_type,
        mime_type=mime_type,
        file_size=file_size,
    )

    repository = MediaRepository(db)

    expires_at = datetime.now(timezone.utc) + _UPLOAD_EXPIRY
    storage_key = _build_storage_key(
        user_id=owner_id,
        media_type=media_type,
    )

    try:
        allocation = storage.allocate_upload(
            storage_key=storage_key,
            mime_type=mime_type,
            file_size=file_size,
            expires_at=expires_at,
        )
    except Exception as exc:
        raise MediaStorageError(
            "Unable to allocate media storage."
        ) from exc

    asset = MediaAsset(
        owner_id=owner_id,
        media_type=media_type,
        mime_type=mime_type,
        file_size=file_size,
        storage_provider=allocation.storage_provider,
        storage_key=allocation.storage_key,
        status="pending",
    )

    repository.add_asset(asset)

    # Materialize the Python-generated asset UUID before creating
    # the dependent MediaUpload row.
    db.flush()

    upload = MediaUpload(
        media_asset_id=asset.id,
        status="pending",
        expires_at=expires_at,
    )

    repository.add_upload(upload)

    try:
        db.commit()
    except Exception:
        db.rollback()

        try:
            storage.delete_object(
                storage_key=allocation.storage_key,
            )
        except Exception:
            pass

        raise

    db.refresh(asset)
    db.refresh(upload)

    return MediaUploadResult(
        asset=asset,
        upload=upload,
        allocation=allocation,
    )


def complete_media_upload(
    db: Session,
    *,
    storage: MediaStorage,
    owner_id: UUID,
    upload_id: UUID,
) -> MediaUploadResult:
    """
    Verify a completed storage upload and advance its media lifecycle.

    Successful completion moves the upload to ``completed`` and the
    associated asset to ``processing``. Processing is a separate lifecycle
    step and must not be inferred merely from upload completion.
    """
    repository = MediaRepository(db)

    upload = repository.get_upload(upload_id)
    if upload is None:
        raise MediaValidationError("Media upload not found.")

    asset = repository.get_asset(upload.media_asset_id)
    if asset is None:
        raise MediaValidationError("Media asset not found.")

    if asset.owner_id != owner_id:
        raise MediaValidationError("Media upload does not belong to this user.")

    if upload.status == "completed":
        raise MediaValidationError("Media upload is already completed.")

    if upload.status in {"failed", "expired"}:
        raise MediaValidationError("Media upload cannot be completed.")

    now = datetime.now(timezone.utc)

    if upload.expires_at <= now:
        upload.status = "expired"
        upload.failed_at = now
        upload.failure_reason = "Upload expired."
        asset.status = "failed"
        db.commit()
        raise MediaValidationError("Media upload has expired.")

    try:
        stored_object = storage.inspect_object(
            storage_key=asset.storage_key,
        )
    except Exception as exc:
        raise MediaStorageError(
            "Unable to inspect uploaded media."
        ) from exc

    if stored_object.storage_provider != asset.storage_provider:
        raise MediaValidationError("Stored media provider does not match.")

    if stored_object.storage_key != asset.storage_key:
        raise MediaValidationError("Stored media key does not match.")

    if stored_object.mime_type != asset.mime_type:
        raise MediaValidationError("Stored media MIME type does not match.")

    if stored_object.file_size != asset.file_size:
        raise MediaValidationError("Stored media file size does not match.")

    upload.status = "completed"
    upload.completed_at = now
    upload.failure_reason = None

    asset.status = "processing"

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(asset)
    db.refresh(upload)

    return MediaUploadResult(
        asset=asset,
        upload=upload,
        allocation=UploadAllocation(
            storage_provider=asset.storage_provider,
            storage_key=asset.storage_key,
            upload_url="",
            expires_at=upload.expires_at,
        ),
    )
