from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register() -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"message-{uuid4().hex}@example.com",
            "password": "VeryStrongPassword123!",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["user_id"], body["session_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_direct_messaging_flow_and_participant_privacy():
    sender_id, sender_token = _register()
    recipient_id, recipient_token = _register()
    _, outsider_token = _register()

    created = client.post(
        "/api/v1/messages/conversations",
        headers=_headers(sender_token),
        json={"recipient_id": recipient_id},
    )
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]

    reopened = client.post(
        "/api/v1/messages/conversations",
        headers=_headers(recipient_token),
        json={"recipient_id": sender_id},
    )
    assert reopened.status_code == 201, reopened.text
    assert reopened.json()["id"] == conversation_id

    sent = client.post(
        f"/api/v1/messages/conversations/{conversation_id}/messages",
        headers=_headers(sender_token),
        json={"body": "Hello from COMMONDEPTH."},
    )
    assert sent.status_code == 201, sent.text
    assert sent.json()["sender_id"] == sender_id
    assert sent.json()["body"] == "Hello from COMMONDEPTH."

    inbox = client.get(
        "/api/v1/messages/conversations",
        headers=_headers(recipient_token),
    )
    assert inbox.status_code == 200, inbox.text
    assert any(item["id"] == conversation_id for item in inbox.json())

    history = client.get(
        f"/api/v1/messages/conversations/{conversation_id}",
        headers=_headers(recipient_token),
    )
    assert history.status_code == 200, history.text
    assert [m["body"] for m in history.json()["messages"]] == [
        "Hello from COMMONDEPTH."
    ]

    forbidden_history = client.get(
        f"/api/v1/messages/conversations/{conversation_id}",
        headers=_headers(outsider_token),
    )
    assert forbidden_history.status_code == 404

    forbidden_send = client.post(
        f"/api/v1/messages/conversations/{conversation_id}/messages",
        headers=_headers(outsider_token),
        json={"body": "I should not be able to send this."},
    )
    assert forbidden_send.status_code == 404


def test_conversation_participants_receive_signed_avatar_urls(monkeypatch):
    from uuid import UUID

    from app.api.dependencies import get_media_storage
    from app.core.database import SessionLocal
    from app.models.media import MediaAsset
    from app.models.profile import Profile

    class MessagingTestStorage:
        def get_read_url(self, *, storage_key: str) -> str:
            return f"https://fake.example/read/{storage_key}"

    monkeypatch.setitem(
        app.dependency_overrides,
        get_media_storage,
        lambda: MessagingTestStorage(),
    )

    uploaded_user_id, uploaded_token = _register()
    legacy_user_id, legacy_token = _register()

    uploaded_username = f"msgavatar_{uuid4().hex[:12]}"
    legacy_username = f"mslegacy_{uuid4().hex[:12]}"
    legacy_avatar = "https://legacy.example/avatar.png"
    asset_id = uuid4()

    try:
        uploaded_profile = client.post(
            "/api/v1/profiles",
            headers=_headers(uploaded_token),
            json={"username": uploaded_username},
        )
        assert uploaded_profile.status_code == 201, uploaded_profile.text

        legacy_profile = client.post(
            "/api/v1/profiles",
            headers=_headers(legacy_token),
            json={
                "username": legacy_username,
                "avatar": legacy_avatar,
            },
        )
        assert legacy_profile.status_code == 201, legacy_profile.text

        db = SessionLocal()
        try:
            asset = MediaAsset(
                id=asset_id,
                owner_id=UUID(str(uploaded_user_id)),
                media_type="image",
                mime_type="image/jpeg",
                file_size=1,
                storage_provider="messaging-test",
                storage_key=f"messaging-test/{asset_id}",
                status="ready",
            )
            db.add(asset)

            profile = db.query(Profile).filter(
                Profile.user_id == UUID(str(uploaded_user_id))
            ).one()
            profile.avatar_asset_id = asset_id
            db.commit()
        finally:
            db.close()

        expected_signed_url = (
            f"https://fake.example/read/messaging-test/{asset_id}"
        )

        created = client.post(
            "/api/v1/messages/conversations",
            headers=_headers(uploaded_token),
            json={"recipient_id": legacy_user_id},
        )
        assert created.status_code == 201, created.text
        conversation_id = created.json()["id"]

        participants = [
            created.json()["participant_one"],
            created.json()["participant_two"],
        ]
        participants_by_id = {
            participant["user_id"]: participant
            for participant in participants
            if participant is not None
        }

        assert participants_by_id[uploaded_user_id]["avatar"] == (
            expected_signed_url
        )
        assert participants_by_id[legacy_user_id]["avatar"] == legacy_avatar

        inbox = client.get(
            "/api/v1/messages/conversations",
            headers=_headers(legacy_token),
        )
        assert inbox.status_code == 200, inbox.text

        conversation = next(
            item for item in inbox.json()
            if item["id"] == conversation_id
        )
        inbox_participants = [
            conversation["participant_one"],
            conversation["participant_two"],
        ]
        inbox_by_id = {
            participant["user_id"]: participant
            for participant in inbox_participants
            if participant is not None
        }

        assert inbox_by_id[uploaded_user_id]["avatar"] == (
            expected_signed_url
        )
        assert inbox_by_id[legacy_user_id]["avatar"] == legacy_avatar

    finally:
        db = SessionLocal()
        try:
            profile = db.query(Profile).filter(
                Profile.user_id == UUID(str(uploaded_user_id))
            ).first()

            if profile is not None:
                profile.avatar_asset_id = None
                db.flush()

            db.query(MediaAsset).filter(
                MediaAsset.id == asset_id
            ).delete(synchronize_session=False)

            db.commit()
        finally:
            db.close()
