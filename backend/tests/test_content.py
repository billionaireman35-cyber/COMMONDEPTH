from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.content import Post
from app.services.content import InvalidPostListError, list_posts_by_author


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_content() -> None:
    db = SessionLocal()
    try:
        db.query(Post).delete()
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


def test_create_public_post() -> None:
    user_id, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "Hello COMMONDEPTH.",
            "visibility": "public",
        },
    )

    assert response.status_code == 201
    body = response.json()

    assert body["author_id"] == user_id
    assert body["content"] == "Hello COMMONDEPTH."
    assert body["visibility"] == "public"
    assert body["id"]
    assert body["created_at"]
    assert body["updated_at"]


def test_create_post_trims_surrounding_whitespace() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "   Hello COMMONDEPTH.   ",
        },
    )

    assert response.status_code == 201
    assert response.json()["content"] == "Hello COMMONDEPTH."


def test_create_post_rejects_whitespace_only_content() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "   \n\t   ",
        },
    )

    assert response.status_code == 422


def test_create_post_rejects_content_over_5000_characters() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "x" * 5001,
        },
    )

    assert response.status_code == 422


def test_create_post_accepts_5000_characters() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "x" * 5000,
        },
    )

    assert response.status_code == 201


def test_create_followers_only_post() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "Followers only.",
            "visibility": "followers",
        },
    )

    assert response.status_code == 201
    assert response.json()["visibility"] == "followers"


def test_create_post_requires_authentication() -> None:
    response = client.post(
        "/api/v1/posts",
        json={
            "content": "Unauthenticated post.",
        },
    )

    assert response.status_code == 401


def test_create_post_cannot_spoof_author_id() -> None:
    user_id, token = _register()
    other_user_id, _ = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "author_id": other_user_id,
            "content": "The server must derive my author ID.",
        },
    )

    assert response.status_code == 422

    db = SessionLocal()
    try:
        assert db.query(Post).filter(Post.author_id == user_id).count() == 0
        assert db.query(Post).filter(Post.author_id == other_user_id).count() == 0
    finally:
        db.close()


def test_create_post_rejects_invalid_visibility() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={
            "content": "Invalid visibility.",
            "visibility": "private",
        },
    )

    assert response.status_code == 422


def _create_post(
    token: str,
    *,
    content: str = "Test post.",
    visibility: str = "public",
):
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


def _follow(
    follower_token: str,
    username: str,
) -> None:
    response = client.post(
        f"/api/v1/social/follow/{username}",
        headers=_auth_header(follower_token),
    )
    assert response.status_code in {200, 201}



def test_list_posts_by_author_uses_default_limit_and_returns_cursor() -> None:
    author_id, token = _register()

    for index in range(21):
        _create_post(token, content=f"Post {index}")

    db = SessionLocal()
    try:
        posts, next_cursor = list_posts_by_author(
            db,
            author_id=__import__("uuid").UUID(author_id),
            viewer_user_id=__import__("uuid").UUID(author_id),
        )
    finally:
        db.close()

    assert len(posts) == 20
    assert next_cursor is not None
    assert posts[0].content == "Post 20"
    assert posts[-1].content == "Post 1"


def test_list_posts_by_author_cursor_returns_next_page() -> None:
    author_id, token = _register()

    for index in range(21):
        _create_post(token, content=f"Post {index}")

    db = SessionLocal()
    try:
        first_page, cursor = list_posts_by_author(
            db,
            author_id=__import__("uuid").UUID(author_id),
            viewer_user_id=__import__("uuid").UUID(author_id),
            limit=20,
        )
        second_page, next_cursor = list_posts_by_author(
            db,
            author_id=__import__("uuid").UUID(author_id),
            viewer_user_id=__import__("uuid").UUID(author_id),
            limit=20,
            cursor=cursor,
        )
    finally:
        db.close()

    assert len(first_page) == 20
    assert len(second_page) == 1
    assert second_page[0].content == "Post 0"
    assert next_cursor is None


def test_list_posts_by_author_rejects_invalid_limit() -> None:
    author_id, _ = _register()

    db = SessionLocal()
    try:
        with pytest.raises(InvalidPostListError):
            list_posts_by_author(
                db,
                author_id=__import__("uuid").UUID(author_id),
                viewer_user_id=__import__("uuid").UUID(author_id),
                limit=0,
            )

        with pytest.raises(InvalidPostListError):
            list_posts_by_author(
                db,
                author_id=__import__("uuid").UUID(author_id),
                viewer_user_id=__import__("uuid").UUID(author_id),
                limit=51,
            )
    finally:
        db.close()


def test_list_posts_by_author_rejects_invalid_cursor() -> None:
    author_id, _ = _register()

    db = SessionLocal()
    try:
        with pytest.raises(InvalidPostListError):
            list_posts_by_author(
                db,
                author_id=__import__("uuid").UUID(author_id),
                viewer_user_id=__import__("uuid").UUID(author_id),
                cursor="not-a-valid-cursor",
            )
    finally:
        db.close()


def test_list_posts_by_author_excludes_deleted_posts() -> None:
    author_id, token = _register()

    first = _create_post(token, content="First")
    second = _create_post(token, content="Second")

    response = client.delete(
        f"/api/v1/posts/{first['id']}",
        headers=_auth_header(token),
    )
    assert response.status_code == 204

    db = SessionLocal()
    try:
        posts, next_cursor = list_posts_by_author(
            db,
            author_id=__import__("uuid").UUID(author_id),
            viewer_user_id=__import__("uuid").UUID(author_id),
        )
    finally:
        db.close()

    assert [post.content for post in posts] == ["Second"]
    assert next_cursor is None




def test_list_user_posts_returns_first_page() -> None:
    author_id, token = _register()

    for index in range(21):
        _create_post(token, content=f"Post {index}")

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body["items"]) == 20
    assert body["next_cursor"] is not None
    assert body["items"][0]["content"] == "Post 20"
    assert body["items"][-1]["content"] == "Post 1"


def test_list_user_posts_cursor_returns_next_page() -> None:
    author_id, token = _register()

    for index in range(21):
        _create_post(token, content=f"Post {index}")

    first_response = client.get(
        f"/api/v1/posts/user/{author_id}",
        headers=_auth_header(token),
    )
    assert first_response.status_code == 200

    first_body = first_response.json()

    second_response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={"cursor": first_body["next_cursor"]},
        headers=_auth_header(token),
    )

    assert second_response.status_code == 200
    second_body = second_response.json()

    assert len(second_body["items"]) == 1
    assert second_body["items"][0]["content"] == "Post 0"
    assert second_body["next_cursor"] is None


def test_list_user_posts_accepts_custom_limit() -> None:
    author_id, token = _register()

    for index in range(6):
        _create_post(token, content=f"Post {index}")

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={"limit": 5},
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body["items"]) == 5
    assert body["next_cursor"] is not None


def test_list_user_posts_rejects_invalid_limit() -> None:
    author_id, token = _register()

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={"limit": 0},
        headers=_auth_header(token),
    )

    assert response.status_code == 422

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={"limit": 51},
        headers=_auth_header(token),
    )

    assert response.status_code == 422


def test_list_user_posts_rejects_invalid_cursor() -> None:
    author_id, token = _register()

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={"cursor": "not-a-valid-cursor"},
        headers=_auth_header(token),
    )

    assert response.status_code == 422


def test_list_user_posts_excludes_deleted_posts() -> None:
    author_id, token = _register()

    first = _create_post(token, content="First")
    _create_post(token, content="Second")

    delete_response = client.delete(
        f"/api/v1/posts/{first['id']}",
        headers=_auth_header(token),
    )
    assert delete_response.status_code == 204

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()

    assert [item["content"] for item in body["items"]] == ["Second"]
    assert body["next_cursor"] is None


def test_list_user_posts_requires_authentication() -> None:
    author_id, _ = _register()

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
    )

    assert response.status_code == 401


def test_list_user_posts_rejects_invalid_user_uuid() -> None:
    _, token = _register()

    response = client.get(
        "/api/v1/posts/user/not-a-uuid",
        headers=_auth_header(token),
    )

    assert response.status_code == 422



def test_list_user_posts_hides_followers_only_posts_from_unrelated_user() -> None:
    author_id, author_token = _register()
    _, viewer_token = _register()

    _create_post(
        author_token,
        content="Public post",
        visibility="public",
    )
    _create_post(
        author_token,
        content="Followers only post",
        visibility="followers",
    )

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["content"] for item in body["items"]] == ["Public post"]


def test_list_user_posts_allows_followers_only_posts_for_accepted_follower() -> None:
    author_id, author_token = _register()
    _, follower_token = _register()

    profile_response = client.post(
        "/api/v1/profiles",
        headers=_auth_header(author_token),
        json={
            "username": f"author_{author_id.replace('-', '')[:20]}",
        },
    )

    assert profile_response.status_code == 201
    username = profile_response.json()["username"]

    _follow(follower_token, username)

    _create_post(
        author_token,
        content="Public post",
        visibility="public",
    )
    _create_post(
        author_token,
        content="Followers only post",
        visibility="followers",
    )

    response = client.get(
        f"/api/v1/posts/user/{author_id}",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["content"] for item in body["items"]] == [
        "Followers only post",
        "Public post",
    ]


def test_list_user_posts_filters_hidden_posts_before_pagination() -> None:
    author_id, author_token = _register()
    _, viewer_token = _register()

    for content, visibility in (
        ("Visible 3", "public"),
        ("Hidden 3", "followers"),
        ("Visible 2", "public"),
        ("Hidden 2", "followers"),
        ("Visible 1", "public"),
        ("Hidden 1", "followers"),
    ):
        _create_post(
            author_token,
            content=content,
            visibility=visibility,
        )

    first_response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={"limit": 2},
        headers=_auth_header(viewer_token),
    )

    assert first_response.status_code == 200
    first_body = first_response.json()
    assert [item["content"] for item in first_body["items"]] == [
        "Visible 1",
        "Visible 2",
    ]
    assert first_body["next_cursor"] is not None

    second_response = client.get(
        f"/api/v1/posts/user/{author_id}",
        params={
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
        headers=_auth_header(viewer_token),
    )

    assert second_response.status_code == 200
    second_body = second_response.json()
    assert [item["content"] for item in second_body["items"]] == ["Visible 3"]
    assert second_body["next_cursor"] is None


def test_get_public_post() -> None:
    _, author_token = _register()
    _, viewer_token = _register()

    post = _create_post(author_token)

    response = client.get(
        f"/api/v1/posts/{post['id']}",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 200
    assert response.json()["id"] == post["id"]


def test_get_followers_only_post_allows_author() -> None:
    _, author_token = _register()

    post = _create_post(
        author_token,
        visibility="followers",
    )

    response = client.get(
        f"/api/v1/posts/{post['id']}",
        headers=_auth_header(author_token),
    )

    assert response.status_code == 200


def test_get_followers_only_post_allows_accepted_follower() -> None:
    author_id, author_token = _register()
    _, follower_token = _register()

    profile = client.post(
        "/api/v1/profiles",
        headers=_auth_header(author_token),
        json={
            "username": f"user{author_id.replace('-', '')[:20]}",
            "display_name": "Author",
        },
    )
    assert profile.status_code == 201
    username = profile.json()["username"]

    follow = client.post(
        f"/api/v1/social/follow/{username}",
        headers=_auth_header(follower_token),
    )
    assert follow.status_code in {200, 201}

    post = _create_post(
        author_token,
        visibility="followers",
    )

    response = client.get(
        f"/api/v1/posts/{post['id']}",
        headers=_auth_header(follower_token),
    )

    assert response.status_code == 200


def test_get_followers_only_post_denies_unrelated_user() -> None:
    _, author_token = _register()
    _, viewer_token = _register()

    post = _create_post(
        author_token,
        visibility="followers",
    )

    response = client.get(
        f"/api/v1/posts/{post['id']}",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 404


def test_get_post_requires_authentication() -> None:
    _, author_token = _register()
    post = _create_post(author_token)

    response = client.get(f"/api/v1/posts/{post['id']}")

    assert response.status_code == 401


def test_get_missing_post_returns_404() -> None:
    _, viewer_token = _register()

    response = client.get(
        f"/api/v1/posts/{uuid4()}",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 404


def test_get_post_rejects_invalid_uuid() -> None:
    _, viewer_token = _register()

    response = client.get(
        "/api/v1/posts/not-a-uuid",
        headers=_auth_header(viewer_token),
    )

    assert response.status_code == 422


def test_delete_post_by_author() -> None:
    _, token = _register()
    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={"content": "Delete me"},
    )
    assert response.status_code == 201

    post_id = response.json()["id"]

    response = client.delete(
        f"/api/v1/posts/{post_id}",
        headers=_auth_header(token),
    )
    assert response.status_code == 204

    response = client.get(
        f"/api/v1/posts/{post_id}",
        headers=_auth_header(token),
    )
    assert response.status_code == 404


def test_delete_post_by_non_author_forbidden() -> None:
    _, author_token = _register()
    _, other_token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(author_token),
        json={"content": "Not yours"},
    )
    assert response.status_code == 201

    post_id = response.json()["id"]

    response = client.delete(
        f"/api/v1/posts/{post_id}",
        headers=_auth_header(other_token),
    )
    assert response.status_code == 403


def test_delete_post_twice_returns_not_found() -> None:
    _, token = _register()

    response = client.post(
        "/api/v1/posts",
        headers=_auth_header(token),
        json={"content": "Delete twice"},
    )
    assert response.status_code == 201

    post_id = response.json()["id"]

    assert client.delete(
        f"/api/v1/posts/{post_id}",
        headers=_auth_header(token),
    ).status_code == 204

    assert client.delete(
        f"/api/v1/posts/{post_id}",
        headers=_auth_header(token),
    ).status_code == 404
