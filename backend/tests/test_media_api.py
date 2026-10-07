from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_media_storage
from app.core.database import SessionLocal
from app.main import app
from app.models.identity import (
    Device,
    PasswordCredential,
    Session,
    User,
    UserIdentity,
)
from app.models.media import MediaAsset, MediaUpload


client = TestClient(app)


class FakeMediaStorage:
    def __init__(self):
        self.allocations = []
        self.objects = {}
        self.deleted_keys = []

    def allocate_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        file_size: int,
        expires_at,
    ):
        from app.integrations.media_storage import UploadAllocation

        allocation = UploadAllocation(
            storage_provider="fake",
            storage_key=storage_key,
            upload_url=f"https://fake.example/upload/{storage_key}",
            expires_at=expires_at,
        )
        self.allocations.append(allocation)
        return allocation

    def inspect_object(self, *, storage_key: str):
        return self.objects[storage_key]

    def delete_object(self, *, storage_key: str):
        self.deleted_keys.append(storage_key)

    def get_read_url(self, *, storage_key: str):
        return f"https://fake.example/read/{storage_key}"


class FailingMediaStorage(FakeMediaStorage):
    def allocate_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        file_size: int,
        expires_at,
    ):
        raise RuntimeError("allocation failed")


class InspectFailingMediaStorage(FakeMediaStorage):
    def inspect_object(self, *, storage_key: str):
        raise RuntimeError("inspection failed")


class StoredObject:
    def __init__(self, *, storage_provider, storage_key, file_size, mime_type):
        self.storage_provider = storage_provider
        self.storage_key = storage_key
        self.file_size = file_size
        self.mime_type = mime_type


@pytest.fixture
def storage():
    value = FakeMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: value
    yield value
    app.dependency_overrides.pop(get_media_storage, None)


def _register(email: str):
    unique_email = email.replace("@", f"+{uuid4().hex}@")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": unique_email,
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["user_id"], body["session_token"]


def _auth_header(session_token: str):
    return {"Authorization": f"Bearer {session_token}"}


def _cleanup_user(user_id: str):
    db = SessionLocal()
    try:
        uid = UUID(user_id)

        db.query(MediaUpload).filter(
            MediaUpload.media_asset_id.in_(
                db.query(MediaAsset.id).filter(MediaAsset.owner_id == uid)
            )
        ).delete(synchronize_session=False)

        db.query(MediaAsset).filter(
            MediaAsset.owner_id == uid
        ).delete(synchronize_session=False)

        db.query(Session).filter(Session.user_id == uid).delete(
            synchronize_session=False
        )
        db.query(Device).filter(Device.user_id == uid).delete(
            synchronize_session=False
        )
        db.query(PasswordCredential).filter(
            PasswordCredential.user_identity_id.in_(
                db.query(UserIdentity.id).filter(UserIdentity.user_id == uid)
            )
        ).delete(synchronize_session=False)
        db.query(UserIdentity).filter(
            UserIdentity.user_id == uid
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id == uid).delete(
            synchronize_session=False
        )

        db.commit()
    finally:
        db.close()


def test_media_upload_requires_authentication(storage):
    response = client.post(
        "/api/v1/media/uploads",
        json={
            "media_type": "image",
            "mime_type": "image/jpeg",
            "file_size": 1024,
        },
    )

    assert response.status_code == 401


def test_media_upload_creation_returns_upload_details(storage):
    user_id, session_token = _register("media-api-create@example.com")

    try:
        response = client.post(
            "/api/v1/media/uploads",
            headers=_auth_header(session_token),
            json={
                "media_type": "image",
                "mime_type": "image/jpeg",
                "file_size": 1024,
            },
        )

        assert response.status_code == 201

        body = response.json()

        assert UUID(body["asset_id"])
        assert UUID(body["upload_id"])
        assert body["storage_provider"] == "fake"
        assert body["storage_key"].startswith(f"media/{user_id}/image/")
        assert body["upload_url"].startswith("https://fake.example/")
        assert body["expires_at"]
    finally:
        _cleanup_user(user_id)


def test_media_upload_rejects_invalid_metadata(storage):
    user_id, session_token = _register("media-api-invalid@example.com")

    try:
        response = client.post(
            "/api/v1/media/uploads",
            headers=_auth_header(session_token),
            json={
                "media_type": "image",
                "mime_type": "image/txt",
                "file_size": 1024,
            },
        )

        assert response.status_code == 422
    finally:
        _cleanup_user(user_id)


def test_media_upload_translates_storage_allocation_failure():
    storage = FailingMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage

    user_id, session_token = _register("media-api-allocation@example.com")

    try:
        response = client.post(
            "/api/v1/media/uploads",
            headers=_auth_header(session_token),
            json={
                "media_type": "image",
                "mime_type": "image/jpeg",
                "file_size": 1024,
            },
        )

        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_media_storage, None)
        _cleanup_user(user_id)


def test_media_upload_completion_succeeds_and_starts_processing(storage):
    user_id, session_token = _register("media-api-complete@example.com")

    try:
        create_response = client.post(
            "/api/v1/media/uploads",
            headers=_auth_header(session_token),
            json={
                "media_type": "image",
                "mime_type": "image/jpeg",
                "file_size": 2048,
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()

        storage.objects[created["storage_key"]] = StoredObject(
            storage_provider="fake",
            storage_key=created["storage_key"],
            file_size=2048,
            mime_type="image/jpeg",
        )

        response = client.post(
            f"/api/v1/media/uploads/{created['upload_id']}/complete",
            headers=_auth_header(session_token),
        )

        assert response.status_code == 200

        body = response.json()

        assert body["asset_id"] == created["asset_id"]
        assert body["upload_id"] == created["upload_id"]
        assert body["upload_status"] == "completed"
        assert body["asset_status"] == "processing"
        assert body["completed_at"]
    finally:
        _cleanup_user(user_id)


def test_media_upload_completion_rejects_wrong_owner(storage):
    owner_id, owner_token = _register("media-api-owner@example.com")
    other_user_id, other_token = _register("media-api-other@example.com")

    try:
        create_response = client.post(
            "/api/v1/media/uploads",
            headers=_auth_header(owner_token),
            json={
                "media_type": "image",
                "mime_type": "image/jpeg",
                "file_size": 1024,
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()

        response = client.post(
            f"/api/v1/media/uploads/{created['upload_id']}/complete",
            headers=_auth_header(other_token),
        )

        assert response.status_code == 403
    finally:
        _cleanup_user(owner_id)
        _cleanup_user(other_user_id)


def test_media_upload_completion_returns_404_for_missing_upload(storage):
    user_id, session_token = _register("media-api-missing@example.com")

    try:
        response = client.post(
            "/api/v1/media/uploads/00000000-0000-0000-0000-000000000000/complete",
            headers=_auth_header(session_token),
        )

        assert response.status_code == 404
    finally:
        _cleanup_user(user_id)


def test_media_upload_completion_translates_inspection_failure():
    storage = InspectFailingMediaStorage()
    app.dependency_overrides[get_media_storage] = lambda: storage

    user_id, session_token = _register("media-api-inspect@example.com")

    try:
        create_response = client.post(
            "/api/v1/media/uploads",
            headers=_auth_header(session_token),
            json={
                "media_type": "image",
                "mime_type": "image/jpeg",
                "file_size": 1024,
            },
        )

        assert create_response.status_code == 201
        created = create_response.json()

        response = client.post(
            f"/api/v1/media/uploads/{created['upload_id']}/complete",
            headers=_auth_header(session_token),
        )

        assert response.status_code == 503
    finally:
        app.dependency_overrides.pop(get_media_storage, None)
        _cleanup_user(user_id)
