from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.story import Story, StoryMedia

client = TestClient(app)


def _register() -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"story-{uuid4().hex}@example.com",
            "password": "VeryStrongPassword123!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    return body["user_id"], body["session_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _profile(token: str) -> str:
    username = f"story{uuid4().hex[:12]}"
    response = client.post(
        "/api/v1/profiles",
        headers=_headers(token),
        json={"username": username, "visibility": "public"},
    )
    assert response.status_code == 201
    return username


def test_publish_text_story():
    _, token = _register()
    _profile(token)

    response = client.post(
        "/api/v1/stories",
        headers=_headers(token),
        json={"text_content": "A thought worth sharing."},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["text_content"] == "A thought worth sharing."
    assert body["media"] == []
    expires = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
    remaining = expires - datetime.now(timezone.utc)
    assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)


def test_home_stories_only_includes_own_and_followed_stories():
    _, viewer_token = _register()
    _profile(viewer_token)

    _, author_token = _register()
    author_username = _profile(author_token)

    _, unrelated_token = _register()
    _profile(unrelated_token)

    own = client.post(
        "/api/v1/stories",
        headers=_headers(viewer_token),
        json={"text_content": "My story"},
    )
    followed = client.post(
        "/api/v1/stories",
        headers=_headers(author_token),
        json={"text_content": "Followed story"},
    )
    unrelated = client.post(
        "/api/v1/stories",
        headers=_headers(unrelated_token),
        json={"text_content": "Unrelated story"},
    )
    assert own.status_code == followed.status_code == unrelated.status_code == 201

    follow_response = client.post(
        f"/api/v1/social/follow/{author_username}",
        headers=_headers(viewer_token),
    )
    assert follow_response.status_code in {200, 201}

    response = client.get(
        "/api/v1/stories/home",
        headers=_headers(viewer_token),
    )
    assert response.status_code == 200
    texts = {item["text_content"] for item in response.json()}
    assert "My story" in texts
    assert "Followed story" in texts
    assert "Unrelated story" not in texts


def test_home_stories_excludes_expired_stories():
    user_id, token = _register()
    _profile(token)

    db = SessionLocal()
    try:
        db.add(
            Story(
                author_id=user_id,
                visibility="public",
                text_content="Expired story",
                expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/stories/home",
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert all(
        item["text_content"] != "Expired story"
        for item in response.json()
    )
