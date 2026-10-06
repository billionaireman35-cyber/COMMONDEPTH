from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.content import Post
from app.models.identity import User
from app.models.profile import Profile
from app.models.social import Follow
from app.repositories.feed import FeedRepository
from app.services.feed import InvalidFeedListError, list_feed_posts


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_feed() -> None:
    db = SessionLocal()
    try:
        db.query(Follow).delete()
        db.query(Post).delete()
        db.query(Profile).delete()
        db.commit()
    finally:
        db.close()


def _db() -> Session:
    return SessionLocal()


def _register(
    *,
    email: str | None = None,
    password: str = "VeryStrongPassword123!",
) -> tuple[str, str]:
    email = email or f"user-{uuid4()}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 201

    body = response.json()
    return body["user_id"], body["session_token"]


def _auth_header(session_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {session_token}"}


def _create_profile(
    token: str,
    username: str,
    *,
    visibility: str = "public",
) -> dict:
    response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(token),
        json={
            "username": username,
            "visibility": visibility,
        },
    )

    assert response.status_code == 201
    return response.json()


def _follow(
    follower_token: str,
    username: str,
) -> None:
    response = client.post(
        f"/api/v1/social/follow/{username}",
        headers=_auth_header(follower_token),
    )

    assert response.status_code in {200, 201}


def _create_post(
    token: str,
    *,
    content: str,
    visibility: str = "public",
) -> dict:
    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": content,
            "visibility": visibility,
        },
    )

    assert response.status_code == 201
    return response.json()


def test_feed_repository_returns_posts_from_followed_author() -> None:
    viewer_id, viewer_token = _register()
    author_id, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")
    _create_post(author_token, content="Alice post.")

    db = _db()
    try:
        posts = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=20,
        )
    finally:
        db.close()

    assert [post.content for post in posts] == ["Alice post."]
    assert posts[0].author_id == UUID(author_id)


def test_feed_repository_excludes_non_followed_author() -> None:
    viewer_id, _ = _register()
    author_id, author_token = _register()

    _create_profile(author_token, "alice")
    _create_post(author_token, content="Alice post.")

    db = _db()
    try:
        posts = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=20,
        )
    finally:
        db.close()

    assert posts == []
    assert author_id


def test_feed_repository_merges_followed_authors_chronologically() -> None:
    viewer_id, viewer_token = _register()

    first_author_id, first_author_token = _register()
    second_author_id, second_author_token = _register()

    _create_profile(first_author_token, "alice")
    _create_profile(second_author_token, "bob")

    _follow(viewer_token, "alice")
    _follow(viewer_token, "bob")

    first_post = _create_post(
        first_author_token,
        content="Alice post.",
    )
    second_post = _create_post(
        second_author_token,
        content="Bob post.",
    )

    db = _db()
    try:
        posts = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=20,
        )
    finally:
        db.close()

    assert [post.id for post in posts] == [
        UUID(second_post["id"]),
        UUID(first_post["id"]),
    ]


def test_feed_repository_excludes_deleted_posts() -> None:
    viewer_id, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    deleted_post = _create_post(
        author_token,
        content="Deleted post.",
    )
    active_post = _create_post(
        author_token,
        content="Active post.",
    )

    response = client.delete(
        f"/api/v1/posts/{deleted_post['id']}",
        headers=_auth_header(author_token),
    )
    assert response.status_code == 204

    db = _db()
    try:
        posts = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=20,
        )
    finally:
        db.close()

    assert [post.content for post in posts] == [
        active_post["content"],
    ]


def test_feed_repository_excludes_inactive_author() -> None:
    viewer_id, viewer_token = _register()
    author_id, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")
    _create_post(author_token, content="Alice post.")

    db = _db()
    try:
        author = db.get(User, UUID(author_id))
        assert author is not None
        author.status = "suspended"
        db.commit()

        posts = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=20,
        )
    finally:
        db.close()

    assert posts == []


def test_feed_repository_returns_followers_only_post_for_follower() -> None:
    viewer_id, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    _create_post(
        author_token,
        content="Followers post.",
        visibility="followers",
    )

    db = _db()
    try:
        posts = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=20,
        )
    finally:
        db.close()

    assert [post.content for post in posts] == [
        "Followers post.",
    ]


def test_feed_repository_cursor_returns_next_page() -> None:
    viewer_id, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    for index in range(3):
        _create_post(
            author_token,
            content=f"Post {index}",
        )

    db = _db()
    try:
        first_page = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=2,
        )

        assert len(first_page) == 2

        cursor_created_at = first_page[-1].created_at
        cursor_post_id = first_page[-1].id

        second_page = FeedRepository(db).list_following_posts(
            viewer_user_id=UUID(viewer_id),
            limit=2,
            cursor_created_at=cursor_created_at,
            cursor_post_id=cursor_post_id,
        )
    finally:
        db.close()

    assert len(second_page) == 1
    assert second_page[0].content == "Post 0"


def test_feed_service_returns_default_page_and_next_cursor() -> None:
    viewer_id, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    for index in range(21):
        _create_post(author_token, content=f"Post {index}")

    db = _db()
    try:
        posts, next_cursor = list_feed_posts(
            db,
            viewer_user_id=UUID(viewer_id),
        )
    finally:
        db.close()

    assert len(posts) == 20
    assert next_cursor is not None


def test_feed_service_respects_custom_limit() -> None:
    viewer_id, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    for index in range(4):
        _create_post(author_token, content=f"Post {index}")

    db = _db()
    try:
        posts, next_cursor = list_feed_posts(
            db,
            viewer_user_id=UUID(viewer_id),
            limit=3,
        )
    finally:
        db.close()

    assert len(posts) == 3
    assert next_cursor is not None


def test_feed_service_cursor_continues_from_previous_page() -> None:
    viewer_id, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    for index in range(3):
        _create_post(author_token, content=f"Post {index}")

    db = _db()
    try:
        first_page, next_cursor = list_feed_posts(
            db,
            viewer_user_id=UUID(viewer_id),
            limit=2,
        )
        assert next_cursor is not None

        second_page, final_cursor = list_feed_posts(
            db,
            viewer_user_id=UUID(viewer_id),
            limit=2,
            cursor=next_cursor,
        )
    finally:
        db.close()

    assert [post.content for post in first_page] == [
        "Post 2",
        "Post 1",
    ]
    assert [post.content for post in second_page] == ["Post 0"]
    assert final_cursor is None


def test_feed_service_rejects_invalid_cursor() -> None:
    viewer_id, _ = _register()

    db = _db()
    try:
        with pytest.raises(
            InvalidFeedListError,
            match="Invalid feed cursor.",
        ):
            list_feed_posts(
                db,
                viewer_user_id=UUID(viewer_id),
                cursor="not-a-valid-cursor",
            )
    finally:
        db.close()


@pytest.mark.parametrize("limit", [0, 51])
def test_feed_service_rejects_invalid_limit(limit: int) -> None:
    viewer_id, _ = _register()

    db = _db()
    try:
        with pytest.raises(
            InvalidFeedListError,
            match="Invalid feed limit.",
        ):
            list_feed_posts(
                db,
                viewer_user_id=UUID(viewer_id),
                limit=limit,
            )
    finally:
        db.close()


def test_feed_service_returns_empty_feed_when_user_follows_no_one() -> None:
    viewer_id, _ = _register()

    db = _db()
    try:
        posts, next_cursor = list_feed_posts(
            db,
            viewer_user_id=UUID(viewer_id),
        )
    finally:
        db.close()

    assert posts == []
    assert next_cursor is None


def test_feed_service_excludes_posts_from_non_followed_authors() -> None:
    viewer_id, _ = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _create_post(author_token, content="Not followed.")

    db = _db()
    try:
        posts, next_cursor = list_feed_posts(
            db,
            viewer_user_id=UUID(viewer_id),
        )
    finally:
        db.close()

    assert posts == []
    assert next_cursor is None


def test_feed_api_requires_authentication() -> None:
    response = client.get("/api/v1/feed")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication failed."


def test_feed_api_returns_empty_feed_when_not_following_anyone() -> None:
    _, viewer_token = _register()

    response = client.get(
        "/api/v1/feed",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "next_cursor": None,
    }


def test_feed_api_returns_posts_from_followed_authors() -> None:
    _, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")
    _create_post(
        author_token,
        content="Alice's feed post.",
    )

    response = client.get(
        "/api/v1/feed",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["items"]) == 1
    assert body["items"][0]["content"] == "Alice's feed post."
    assert body["items"][0]["visibility"] == "public"
    assert body["next_cursor"] is None


def test_feed_api_excludes_non_followed_authors() -> None:
    _, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _create_post(
        author_token,
        content="Alice's post.",
    )

    response = client.get(
        "/api/v1/feed",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "next_cursor": None,
    }


def test_feed_api_respects_custom_limit_and_returns_cursor() -> None:
    _, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    for index in range(4):
        _create_post(
            author_token,
            content=f"Feed post {index}",
        )

    response = client.get(
        "/api/v1/feed?limit=2",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None


def test_feed_api_cursor_returns_next_page() -> None:
    _, viewer_token = _register()
    _, author_token = _register()

    _create_profile(author_token, "alice")
    _follow(viewer_token, "alice")

    for index in range(4):
        _create_post(
            author_token,
            content=f"Feed post {index}",
        )

    first_response = client.get(
        "/api/v1/feed?limit=2",
        headers=_auth_header(viewer_token),
    )

    assert first_response.status_code == 200

    first_body = first_response.json()
    assert len(first_body["items"]) == 2
    assert first_body["next_cursor"] is not None

    second_response = client.get(
        "/api/v1/feed",
        headers=_auth_header(viewer_token),
        params={
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
    )

    assert second_response.status_code == 200

    second_body = second_response.json()

    assert len(second_body["items"]) == 2

    first_page_ids = {
        item["id"]
        for item in first_body["items"]
    }
    second_page_ids = {
        item["id"]
        for item in second_body["items"]
    }

    assert first_page_ids.isdisjoint(second_page_ids)
    assert second_body["next_cursor"] is None


def test_feed_api_rejects_invalid_cursor() -> None:
    _, viewer_token = _register()

    response = client.get(
        "/api/v1/feed",
        headers=_auth_header(viewer_token),
        params={"cursor": "not-a-valid-cursor"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid feed cursor."


@pytest.mark.parametrize("limit", [0, 51])
def test_feed_api_rejects_invalid_limit(
    limit: int,
) -> None:
    _, viewer_token = _register()

    response = client.get(
        "/api/v1/feed",
        headers=_auth_header(viewer_token),
        params={"limit": limit},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid feed limit."
