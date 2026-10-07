from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.integrations.media_storage import StorageObject, UploadAllocation
from app.models.identity import (
    Device,
    PasswordCredential,
    Session as IdentitySession,
    UserIdentity,
)
from app.models.media import MediaAsset, MediaUpload
from app.models.identity import User
from app.services.identity_registration import register_identity
from app.services.media import (
    MediaStorageError,
    MediaValidationError,
    complete_media_upload,
    create_media_upload,
)


class FakeMediaStorage:
    def __init__(self) -> None:
        self.allocations: list[UploadAllocation] = []
        self.deleted_keys: list[str] = []
        self.objects: dict[str, StorageObject] = {}

    def allocate_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        file_size: int,
        expires_at: object,
    ) -> UploadAllocation:
        allocation = UploadAllocation(
            storage_provider="fake",
            storage_key=storage_key,
            upload_url=f"https://fake-storage.local/upload/{storage_key}",
            expires_at=expires_at,
        )
        self.allocations.append(allocation)
        return allocation

    def inspect_object(
        self,
        *,
        storage_key: str,
    ) -> StorageObject:
        return self.objects[storage_key]

    def delete_object(
        self,
        *,
        storage_key: str,
    ) -> None:
        self.deleted_keys.append(storage_key)

    def get_read_url(
        self,
        *,
        storage_key: str,
    ) -> str:
        return f"https://fake-storage.local/read/{storage_key}"


class FailingMediaStorage(FakeMediaStorage):
    def allocate_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        file_size: int,
        expires_at: object,
    ) -> UploadAllocation:
        raise RuntimeError("storage unavailable")


class InspectFailingMediaStorage(FakeMediaStorage):
    def inspect_object(
        self,
        *,
        storage_key: str,
    ) -> StorageObject:
        raise RuntimeError("storage inspection unavailable")


def _create_test_user():
    db = SessionLocal()
    email = f"media-service-{uuid4()}@example.invalid"

    result = register_identity(
        db,
        email=email,
        password="CommonDepth-Test-Password-2026!",
    )

    db.close()
    return result.user_id


def _cleanup_user(user_id) -> None:
    db = SessionLocal()
    try:
        asset_ids = db.scalars(
            select(MediaAsset.id).where(
                MediaAsset.owner_id == user_id
            )
        ).all()

        if asset_ids:
            db.execute(
                delete(MediaUpload).where(
                    MediaUpload.media_asset_id.in_(asset_ids)
                )
            )
            db.execute(
                delete(MediaAsset).where(
                    MediaAsset.id.in_(asset_ids)
                )
            )

        db.execute(
            delete(IdentitySession).where(
                IdentitySession.user_id == user_id
            )
        )
        db.execute(
            delete(Device).where(
                Device.user_id == user_id
            )
        )

        identity_ids = db.scalars(
            select(UserIdentity.id).where(
                UserIdentity.user_id == user_id
            )
        ).all()

        if identity_ids:
            db.execute(
                delete(PasswordCredential).where(
                    PasswordCredential.user_identity_id.in_(identity_ids)
                )
            )
            db.execute(
                delete(UserIdentity).where(
                    UserIdentity.id.in_(identity_ids)
                )
            )

        db.execute(
            delete(User).where(User.id == user_id)
        )

        db.commit()
    finally:
        db.close()


def test_create_media_upload_creates_pending_asset_and_upload():
    user_id = _create_test_user()
    db = SessionLocal()
    storage = FakeMediaStorage()

    try:
        result = create_media_upload(
            db,
            storage=storage,
            owner_id=user_id,
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024,
        )

        assert result.asset.owner_id == user_id
        assert result.asset.media_type == "image"
        assert result.asset.mime_type == "image/jpeg"
        assert result.asset.file_size == 1024
        assert result.asset.status == "pending"

        assert result.upload.media_asset_id == result.asset.id
        assert result.upload.status == "pending"
        assert result.upload.expires_at > datetime.now(timezone.utc)

        assert result.allocation.storage_provider == "fake"
        assert result.allocation.storage_key == result.asset.storage_key
        assert len(storage.allocations) == 1

    finally:
        db.close()
        _cleanup_user(user_id)


def test_create_media_upload_rejects_unsupported_media_type():
    db = SessionLocal()

    try:
        with pytest.raises(MediaValidationError):
            create_media_upload(
                db,
                storage=FakeMediaStorage(),
                owner_id=uuid4(),
                media_type="document",
                mime_type="application/pdf",
                file_size=1024,
            )
    finally:
        db.close()


def test_create_media_upload_rejects_mismatched_mime_type():
    db = SessionLocal()

    try:
        with pytest.raises(MediaValidationError):
            create_media_upload(
                db,
                storage=FakeMediaStorage(),
                owner_id=uuid4(),
                media_type="image",
                mime_type="video/mp4",
                file_size=1024,
            )
    finally:
        db.close()


def test_create_media_upload_rejects_oversized_file():
    db = SessionLocal()

    try:
        with pytest.raises(MediaValidationError):
            create_media_upload(
                db,
                storage=FakeMediaStorage(),
                owner_id=uuid4(),
                media_type="image",
                mime_type="image/jpeg",
                file_size=(10 * 1024 * 1024) + 1,
            )
    finally:
        db.close()


def test_create_media_upload_translates_storage_failure():
    db = SessionLocal()

    try:
        with pytest.raises(MediaStorageError):
            create_media_upload(
                db,
                storage=FailingMediaStorage(),
                owner_id=uuid4(),
                media_type="video",
                mime_type="video/mp4",
                file_size=1024,
            )
    finally:
        db.close()


def test_complete_media_upload_verifies_storage_and_starts_processing():
    user_id = _create_test_user()
    db = SessionLocal()
    storage = FakeMediaStorage()

    try:
        created = create_media_upload(
            db,
            storage=storage,
            owner_id=user_id,
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024,
        )

        storage.objects[created.asset.storage_key] = StorageObject(
            storage_provider="fake",
            storage_key=created.asset.storage_key,
            file_size=1024,
            mime_type="image/jpeg",
        )

        result = complete_media_upload(
            db,
            storage=storage,
            owner_id=user_id,
            upload_id=created.upload.id,
        )

        assert result.upload.status == "completed"
        assert result.upload.completed_at is not None
        assert result.asset.status == "processing"

    finally:
        db.close()
        _cleanup_user(user_id)


def test_complete_media_upload_rejects_wrong_owner():
    owner_id = _create_test_user()
    other_user_id = _create_test_user()
    db = SessionLocal()
    storage = FakeMediaStorage()

    try:
        created = create_media_upload(
            db,
            storage=storage,
            owner_id=owner_id,
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024,
        )

        with pytest.raises(MediaValidationError):
            complete_media_upload(
                db,
                storage=storage,
                owner_id=other_user_id,
                upload_id=created.upload.id,
            )

    finally:
        db.close()
        _cleanup_user(owner_id)
        _cleanup_user(other_user_id)


def test_complete_media_upload_rejects_storage_metadata_mismatch():
    user_id = _create_test_user()
    db = SessionLocal()
    storage = FakeMediaStorage()

    try:
        created = create_media_upload(
            db,
            storage=storage,
            owner_id=user_id,
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024,
        )

        storage.objects[created.asset.storage_key] = StorageObject(
            storage_provider="fake",
            storage_key=created.asset.storage_key,
            file_size=2048,
            mime_type="image/jpeg",
        )

        with pytest.raises(MediaValidationError):
            complete_media_upload(
                db,
                storage=storage,
                owner_id=user_id,
                upload_id=created.upload.id,
            )

    finally:
        db.close()
        _cleanup_user(user_id)


def test_complete_media_upload_translates_storage_inspection_failure():
    user_id = _create_test_user()
    db = SessionLocal()
    storage = InspectFailingMediaStorage()

    try:
        created = create_media_upload(
            db,
            storage=storage,
            owner_id=user_id,
            media_type="video",
            mime_type="video/mp4",
            file_size=1024,
        )

        with pytest.raises(MediaStorageError):
            complete_media_upload(
                db,
                storage=storage,
                owner_id=user_id,
                upload_id=created.upload.id,
            )

    finally:
        db.close()
        _cleanup_user(user_id)
