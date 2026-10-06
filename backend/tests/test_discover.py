from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.content import Post
from app.models.identity import User
from app.models.profile import Profile
from app.services.discover import (
    InvalidDiscoverListError,
    list_discover_posts,
)
from app.repositories.discover import DiscoverRepository


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_discover() -> None:
    db = SessionLocal()
    try:
        db.query(Post).delete()
        db.query(Profile).delete()
        db.commit()
    finally:
        db.close()


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


def test_discover_repository_returns_public_posts() -> None:
    _, author_token = _register()

    public_post = _create_post(
        author_token,
        content="Public post.",
    )

    db = SessionLocal()
    try:
        posts = DiscoverRepository(db).list_public_posts(limit=20)
    finally:
        db.close()

    assert [post.id for post in posts] == [
        UUID(public_post["id"]),
    ]


def test_discover_repository_excludes_followers_only_posts() -> None:
    _, author_token = _register()

    _create_post(
        author_token,
        content="Followers only.",
        visibility="followers",
    )

    db = SessionLocal()
    try:
        posts = DiscoverRepository(db).list_public_posts(limit=20)
    finally:
        db.close()

    assert posts == []


def test_discover_repository_excludes_deleted_posts() -> None:
    _, author_token = _register()

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

    db = SessionLocal()
    try:
        posts = DiscoverRepository(db).list_public_posts(limit=20)
    finally:
        db.close()

    assert [post.content for post in posts] == [
        active_post["content"],
    ]


def test_discover_repository_excludes_inactive_authors() -> None:
    author_id, author_token = _register()

    _create_post(
        author_token,
        content="Inactive author post.",
    )

    db = SessionLocal()
    try:
        author = db.get(User, UUID(author_id))
        assert author is not None

        author.status = "suspended"
        db.commit()

        posts = DiscoverRepository(db).list_public_posts(limit=20)
    finally:
        db.close()

    assert posts == []


def test_discover_repository_cursor_returns_next_page() -> None:
    _, author_token = _register()

    for index in range(3):
        _create_post(
            author_token,
            content=f"Post {index}",
        )

    db = SessionLocal()
    try:
        first_page = DiscoverRepository(db).list_public_posts(
            limit=2,
        )

        assert len(first_page) == 2

        second_page = DiscoverRepository(db).list_public_posts(
            limit=2,
            cursor_created_at=first_page[-1].created_at,
            cursor_post_id=first_page[-1].id,
        )
    finally:
        db.close()

    assert len(second_page) == 1
    assert second_page[0].content == "Post 0"


def test_discover_service_returns_default_page_and_cursor() -> None:
    _, author_token = _register()

    for index in range(21):
        _create_post(
            author_token,
            content=f"Post {index}",
        )

    db = SessionLocal()
    try:
        posts, next_cursor = list_discover_posts(db)
    finally:
        db.close()

    assert len(posts) == 20
    assert next_cursor is not None
    assert posts[0].content == "Post 20"
    assert posts[-1].content == "Post 1"


def test_discover_service_cursor_returns_next_page() -> None:
    _, author_token = _register()

    for index in range(21):
        _create_post(
            author_token,
            content=f"Post {index}",
        )

    db = SessionLocal()
    try:
        first_page, cursor = list_discover_posts(
            db,
            limit=20,
        )

        second_page, next_cursor = list_discover_posts(
            db,
            limit=20,
            cursor=cursor,
        )
    finally:
        db.close()

    assert len(first_page) == 20
    assert len(second_page) == 1
    assert second_page[0].content == "Post 0"
    assert next_cursor is None


def test_discover_service_rejects_invalid_limit() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(InvalidDiscoverListError):
            list_discover_posts(db, limit=0)

        with pytest.raises(InvalidDiscoverListError):
            list_discover_posts(db, limit=51)
    finally:
        db.close()


def test_discover_service_rejects_invalid_cursor() -> None:
    db = SessionLocal()
    try:
        with pytest.raises(InvalidDiscoverListError):
            list_discover_posts(
                db,
                cursor="not-a-valid-cursor",
            )
    finally:
        db.close()


def test_discover_endpoint_returns_public_posts() -> None:
    _, author_token = _register()

    _create_post(
        author_token,
        content="Discover this post.",
    )

    response = client.get(
        "/api/v1/discover",
        headers=_auth_header(author_token),
    )

    assert response.status_code == 200

    body = response.json()

    assert len(body["items"]) == 1
    assert body["items"][0]["content"] == "Discover this post."
    assert body["items"][0]["visibility"] == "public"
    assert body["next_cursor"] is None


def test_discover_endpoint_requires_authentication() -> None:
    response = client.get("/api/v1/discover")

    assert response.status_code == 401


def test_discover_endpoint_rejects_invalid_limit() -> None:
    _, token = _register()

    response = client.get(
        "/api/v1/discover?limit=0",
        headers=_auth_header(token),
    )

    assert response.status_code == 422


def test_discover_endpoint_supports_cursor_pagination() -> None:
    _, author_token = _register()

    for index in range(21):
        _create_post(
            author_token,
            content=f"Discover post {index}",
        )

    headers = _auth_header(author_token)

    first_response = client.get(
        "/api/v1/discover?limit=20",
        headers=headers,
    )

    assert first_response.status_code == 200

    first_body = first_response.json()

    assert len(first_body["items"]) == 20
    assert first_body["next_cursor"] is not None

    second_response = client.get(
        f"/api/v1/discover?limit=20&cursor={first_body['next_cursor']}",
        headers=headers,
    )

    assert second_response.status_code == 200

    second_body = second_response.json()

    assert len(second_body["items"]) == 1
    assert second_body["items"][0]["content"] == "Discover post 0"
    assert second_body["next_cursor"] is None
