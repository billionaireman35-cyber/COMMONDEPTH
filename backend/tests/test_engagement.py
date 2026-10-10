from uuid import uuid4

import pytest

from app.core.database import SessionLocal
from app.models.content import Post, PostBookmark, PostComment, PostRepost
from app.models.identity import User
from app.services.content import PostAccessDeniedError
from app.services.engagement import (
    EngagementUserInactiveError,
    InvalidPostCommentError,
    PostCommentNotFoundError,
    PostCommentUnauthorizedError,
    comment_on_post,
    delete_post_comment,
    list_post_comments,
)
from app.services.identity_registration import register_identity


def _create_user() -> uuid4:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=f"engagement-{uuid4()}@example.invalid",
            password="CommonDepth-Test-Password-2026!",
        )
        return result.user_id
    finally:
        db.close()


def _create_post(
    *,
    author_id,
    visibility: str = "public",
):
    db = SessionLocal()
    try:
        post = Post(
            author_id=author_id,
            content="Test post.",
            visibility=visibility,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return post.id
    finally:
        db.close()


def _deactivate_user(user_id) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        assert user is not None
        user.status = "suspended"
        db.commit()
    finally:
        db.close()


def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(PostComment).delete()
        db.query(PostBookmark).delete()
        db.query(PostRepost).delete()
        db.query(Post).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_engagement() -> None:
    _cleanup()
    yield
    _cleanup()


def test_comment_on_post_creates_real_comment() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        comment = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="Hello COMMONDEPTH.",
        )

        assert comment.post_id == post_id
        assert comment.user_id == user_id
        assert comment.content == "Hello COMMONDEPTH."
        assert comment.deleted_at is None
    finally:
        db.close()


def test_comment_on_post_trims_whitespace() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        comment = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="   Hello COMMONDEPTH.   ",
        )

        assert comment.content == "Hello COMMONDEPTH."
    finally:
        db.close()


@pytest.mark.parametrize("content", ["", "   ", "\n\t"])
def test_comment_on_post_rejects_empty_content(content: str) -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        with pytest.raises(InvalidPostCommentError):
            comment_on_post(
                db,
                post_id=post_id,
                user_id=user_id,
                content=content,
            )
    finally:
        db.close()


def test_comment_on_post_rejects_over_1000_characters() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        with pytest.raises(InvalidPostCommentError):
            comment_on_post(
                db,
                post_id=post_id,
                user_id=user_id,
                content="x" * 1001,
            )
    finally:
        db.close()


def test_comment_on_post_accepts_1000_characters() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        comment = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="x" * 1000,
        )

        assert len(comment.content) == 1000
    finally:
        db.close()


def test_comment_on_followers_only_post_denies_unrelated_user() -> None:
    author_id = _create_user()
    viewer_id = _create_user()
    post_id = _create_post(
        author_id=author_id,
        visibility="followers",
    )

    db = SessionLocal()
    try:
        with pytest.raises(PostAccessDeniedError):
            comment_on_post(
                db,
                post_id=post_id,
                user_id=viewer_id,
                content="Not allowed.",
            )
    finally:
        db.close()


def test_comment_rejects_inactive_user() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)
    _deactivate_user(user_id)

    db = SessionLocal()
    try:
        with pytest.raises(EngagementUserInactiveError):
            comment_on_post(
                db,
                post_id=post_id,
                user_id=user_id,
                content="Inactive.",
            )
    finally:
        db.close()


def test_list_post_comments_returns_newest_first() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        first = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="First.",
        )
        second = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="Second.",
        )

        comments, next_cursor = list_post_comments(
            db,
            post_id=post_id,
            viewer_user_id=user_id,
            limit=10,
        )

        assert next_cursor is None
        assert [comment.id for comment in comments] == [
            second.id,
            first.id,
        ]
    finally:
        db.close()


def test_list_post_comments_uses_cursor_pagination() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        first = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="First.",
        )
        second = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="Second.",
        )
        third = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="Third.",
        )

        page_one, next_cursor = list_post_comments(
            db,
            post_id=post_id,
            viewer_user_id=user_id,
            limit=2,
        )

        assert next_cursor is not None
        assert [comment.id for comment in page_one] == [
            third.id,
            second.id,
        ]

        page_two, page_two_cursor = list_post_comments(
            db,
            post_id=post_id,
            viewer_user_id=user_id,
            limit=2,
            cursor=next_cursor,
        )

        assert page_two_cursor is None
        assert [comment.id for comment in page_two] == [first.id]
    finally:
        db.close()


def test_delete_post_comment_soft_deletes_comment() -> None:
    user_id = _create_user()
    post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        comment = comment_on_post(
            db,
            post_id=post_id,
            user_id=user_id,
            content="Delete me.",
        )

        delete_post_comment(
            db,
            post_id=post_id,
            comment_id=comment.id,
            user_id=user_id,
        )

        stored = db.get(PostComment, comment.id)
        assert stored is not None
        assert stored.deleted_at is not None

        visible, next_cursor = list_post_comments(
            db,
            post_id=post_id,
            viewer_user_id=user_id,
            limit=10,
        )
        assert visible == []
        assert next_cursor is None
    finally:
        db.close()


def test_delete_post_comment_requires_author() -> None:
    author_id = _create_user()
    other_user_id = _create_user()
    post_id = _create_post(author_id=author_id)

    db = SessionLocal()
    try:
        comment = comment_on_post(
            db,
            post_id=post_id,
            user_id=author_id,
            content="Protected.",
        )

        with pytest.raises(PostCommentUnauthorizedError):
            delete_post_comment(
                db,
                post_id=post_id,
                comment_id=comment.id,
                user_id=other_user_id,
            )
    finally:
        db.close()


def test_delete_post_comment_rejects_mismatched_post_id() -> None:
    user_id = _create_user()
    actual_post_id = _create_post(author_id=user_id)
    other_post_id = _create_post(author_id=user_id)

    db = SessionLocal()
    try:
        comment = comment_on_post(
            db,
            post_id=actual_post_id,
            user_id=user_id,
            content="Do not delete through another post.",
        )

        with pytest.raises(PostCommentNotFoundError):
            delete_post_comment(
                db,
                post_id=other_post_id,
                comment_id=comment.id,
                user_id=user_id,
            )

        stored = db.get(PostComment, comment.id)
        assert stored is not None
        assert stored.deleted_at is None
    finally:
        db.close()
