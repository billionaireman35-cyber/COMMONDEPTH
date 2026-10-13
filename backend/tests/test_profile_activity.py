from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.content import Post, PostComment, PostRepost

client = TestClient(app)


@pytest.fixture
def activity_data():
    """Track and clean up only posts created by this fixture."""
    post_ids: list[UUID] = []
    yield post_ids

    db = SessionLocal()
    try:
        if post_ids:
            db.query(PostComment).filter(
                PostComment.post_id.in_(post_ids)
            ).delete(synchronize_session=False)

            db.query(PostRepost).filter(
                PostRepost.post_id.in_(post_ids)
            ).delete(synchronize_session=False)

            db.query(Post).filter(
                Post.id.in_(post_ids)
            ).delete(synchronize_session=False)

            db.commit()
    finally:
        db.close()


def _register() -> tuple[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"profile-activity-{uuid4()}@example.com",
            "password": "VeryStrongPassword123!",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["user_id"], body["session_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_post(
    token: str,
    post_ids: list[UUID],
    *,
    content: str,
) -> dict:
    response = client.post(
        "/api/v1/posts",
        headers=_headers(token),
        json={"content": content, "visibility": "public"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    post_ids.append(UUID(body["id"]))
    return body


def _add_comment(
    *,
    post_id: UUID,
    user_id: str,
    content: str,
    created_at: datetime,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            PostComment(
                post_id=post_id,
                user_id=UUID(user_id),
                content=content,
                created_at=created_at,
            )
        )
        db.commit()
    finally:
        db.close()


def _add_repost(
    *,
    post_id: UUID,
    user_id: str,
    created_at: datetime,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            PostRepost(
                post_id=post_id,
                user_id=UUID(user_id),
                created_at=created_at,
            )
        )
        db.commit()
    finally:
        db.close()


def test_profile_replies_returns_comment_and_original_post(
    activity_data: list[UUID],
) -> None:
    user_id, token = _register()
    post = _create_post(
        token,
        activity_data,
        content="Original post for a reply",
    )
    _add_comment(
        post_id=UUID(post["id"]),
        user_id=user_id,
        content="My profile reply",
        created_at=datetime.now(timezone.utc),
    )

    response = client.get(
        f"/api/v1/posts/user/{user_id}/replies",
        headers=_headers(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["content"] == "My profile reply"
    assert item["post_id"] == post["id"]
    assert item["post"]["id"] == post["id"]
    assert item["post"]["content"] == "Original post for a reply"
    assert "next_cursor" in body


def test_profile_reposts_returns_reposted_original_post(
    activity_data: list[UUID],
) -> None:
    user_id, token = _register()
    post = _create_post(
        token,
        activity_data,
        content="Original post for a repost",
    )
    _add_repost(
        post_id=UUID(post["id"]),
        user_id=user_id,
        created_at=datetime.now(timezone.utc),
    )

    response = client.get(
        f"/api/v1/posts/user/{user_id}/reposts",
        headers=_headers(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["post"]["id"] == post["id"]
    assert item["post"]["content"] == "Original post for a repost"
    assert item["repost_id"]
    assert item["reposted_at"]
    assert "next_cursor" in body


@pytest.mark.parametrize("activity", ["replies", "reposts"])
def test_profile_activity_requires_authentication(
    activity: str,
) -> None:
    user_id, _ = _register()

    response = client.get(
        f"/api/v1/posts/user/{user_id}/{activity}",
    )

    assert response.status_code == 401, response.text


@pytest.mark.parametrize("activity", ["replies", "reposts"])
def test_profile_activity_rejects_invalid_cursor(
    activity: str,
) -> None:
    user_id, token = _register()

    response = client.get(
        f"/api/v1/posts/user/{user_id}/{activity}",
        headers=_headers(token),
        params={"cursor": "not-a-valid-cursor"},
    )

    assert response.status_code == 422, response.text


def test_profile_replies_supports_cursor_pagination(
    activity_data: list[UUID],
) -> None:
    user_id, token = _register()

    first_post = _create_post(
        token, activity_data, content="First original post"
    )
    second_post = _create_post(
        token, activity_data, content="Second original post"
    )

    now = datetime.now(timezone.utc)
    _add_comment(
        post_id=UUID(first_post["id"]),
        user_id=user_id,
        content="Older reply",
        created_at=now - timedelta(minutes=2),
    )
    _add_comment(
        post_id=UUID(second_post["id"]),
        user_id=user_id,
        content="Newer reply",
        created_at=now - timedelta(minutes=1),
    )

    first_page = client.get(
        f"/api/v1/posts/user/{user_id}/replies",
        headers=_headers(token),
        params={"limit": 1},
    )

    assert first_page.status_code == 200, first_page.text
    first_body = first_page.json()
    assert len(first_body["items"]) == 1
    assert first_body["items"][0]["content"] == "Newer reply"
    assert first_body["next_cursor"]

    second_page = client.get(
        f"/api/v1/posts/user/{user_id}/replies",
        headers=_headers(token),
        params={
            "limit": 1,
            "cursor": first_body["next_cursor"],
        },
    )

    assert second_page.status_code == 200, second_page.text
    second_body = second_page.json()
    assert len(second_body["items"]) == 1
    assert second_body["items"][0]["content"] == "Older reply"
    assert second_body["next_cursor"] is None
