from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.content import Post
from app.models.identity import (
    Device,
    PasswordCredential,
    Session as IdentitySession,
    User,
    UserIdentity,
)
from app.models.media import MediaAsset, MediaUpload, PostMedia
from app.services.content import create_post
from app.services.identity_registration import register_identity
from app.services.post_media import (
    PostMediaAccessDeniedError,
    PostMediaNotFoundError,
    PostMediaValidationError,
    attach_media_to_post,
)


def _create_test_user() -> object:
    db = SessionLocal()
    try:
        result = register_identity(
            db,
            email=f"post-media-{uuid4()}@example.invalid",
            password="CommonDepth-Test-Password-2026!",
        )
        return result.user_id
    finally:
        db.close()


def _create_post(user_id):
    db = SessionLocal()
    try:
        post = create_post(
            db,
            user_id=user_id,
            content="Post media attachment test post",
            visibility="public",
        )
        return post.id
    finally:
        db.close()


def _create_media(
    user_id,
    *,
    status="processing",
    upload_status="completed",
):
    db = SessionLocal()
    try:
        asset = MediaAsset(
            owner_id=user_id,
            media_type="image",
            mime_type="image/jpeg",
            file_size=1024,
            storage_provider="fake",
            storage_key=f"media/test/{uuid4()}",
            status=status,
        )
        db.add(asset)
        db.flush()

        upload = MediaUpload(
            media_asset_id=asset.id,
            status=upload_status,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        db.add(upload)
        db.commit()

        return asset.id
    finally:
        db.close()


def _cleanup_user(user_id) -> None:
    db = SessionLocal()
    try:
        post_ids = db.scalars(
            select(Post.id).where(Post.author_id == user_id)
        ).all()

        if post_ids:
            db.execute(
                delete(PostMedia).where(PostMedia.post_id.in_(post_ids))
            )
            db.execute(
                delete(Post).where(Post.id.in_(post_ids))
            )

        asset_ids = db.scalars(
            select(MediaAsset.id).where(MediaAsset.owner_id == user_id)
        ).all()

        if asset_ids:
            db.execute(
                delete(PostMedia).where(
                    PostMedia.media_asset_id.in_(asset_ids)
                )
            )
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
            delete(Device).where(Device.user_id == user_id)
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


def test_attach_media_to_post_succeeds():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        asset_id = _create_media(user_id)

        db = SessionLocal()
        try:
            attachment = attach_media_to_post(
                db,
                post_id=post_id,
                media_asset_id=asset_id,
                user_id=user_id,
                position=0,
            )

            assert attachment.id is not None
            assert attachment.post_id == post_id
            assert attachment.media_asset_id == asset_id
            assert attachment.position == 0
            assert attachment.created_at is not None
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_missing_post():
    user_id = _create_test_user()

    try:
        asset_id = _create_media(user_id)
        db = SessionLocal()

        try:
            with pytest.raises(PostMediaNotFoundError):
                attach_media_to_post(
                    db,
                    post_id=uuid4(),
                    media_asset_id=asset_id,
                    user_id=user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_missing_asset():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        db = SessionLocal()

        try:
            with pytest.raises(PostMediaNotFoundError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=uuid4(),
                    user_id=user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_post_owned_by_another_user():
    owner_id = _create_test_user()
    other_user_id = _create_test_user()

    try:
        post_id = _create_post(owner_id)
        asset_id = _create_media(other_user_id)

        db = SessionLocal()
        try:
            with pytest.raises(PostMediaAccessDeniedError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=asset_id,
                    user_id=other_user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(owner_id)
        _cleanup_user(other_user_id)


def test_attach_media_rejects_asset_owned_by_another_user():
    owner_id = _create_test_user()
    other_user_id = _create_test_user()

    try:
        post_id = _create_post(owner_id)
        asset_id = _create_media(owner_id)

        db = SessionLocal()
        try:
            with pytest.raises(PostMediaAccessDeniedError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=asset_id,
                    user_id=other_user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(owner_id)
        _cleanup_user(other_user_id)


@pytest.mark.parametrize(
    ("asset_status", "upload_status"),
    [
        ("pending", "pending"),
        ("failed", "completed"),
        ("deleted", "completed"),
    ],
)
def test_attach_media_rejects_unavailable_asset(
    asset_status,
    upload_status,
):
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        asset_id = _create_media(
            user_id,
            status=asset_status,
            upload_status=upload_status,
        )

        db = SessionLocal()
        try:
            with pytest.raises(PostMediaValidationError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=asset_id,
                    user_id=user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_incomplete_upload():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        asset_id = _create_media(
            user_id,
            status="processing",
            upload_status="pending",
        )

        db = SessionLocal()
        try:
            with pytest.raises(PostMediaValidationError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=asset_id,
                    user_id=user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_duplicate_asset():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        asset_id = _create_media(user_id)

        db = SessionLocal()
        try:
            attach_media_to_post(
                db,
                post_id=post_id,
                media_asset_id=asset_id,
                user_id=user_id,
                position=0,
            )

            with pytest.raises(PostMediaValidationError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=asset_id,
                    user_id=user_id,
                    position=1,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_duplicate_position():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        first_asset_id = _create_media(user_id)
        second_asset_id = _create_media(user_id)

        db = SessionLocal()
        try:
            attach_media_to_post(
                db,
                post_id=post_id,
                media_asset_id=first_asset_id,
                user_id=user_id,
                position=0,
            )

            with pytest.raises(PostMediaValidationError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=second_asset_id,
                    user_id=user_id,
                    position=0,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_rejects_negative_position():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        asset_id = _create_media(user_id)

        db = SessionLocal()
        try:
            with pytest.raises(PostMediaValidationError):
                attach_media_to_post(
                    db,
                    post_id=post_id,
                    media_asset_id=asset_id,
                    user_id=user_id,
                    position=-1,
                )
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)


def test_attach_media_allows_multiple_assets_at_distinct_positions():
    user_id = _create_test_user()

    try:
        post_id = _create_post(user_id)
        first_asset_id = _create_media(user_id)
        second_asset_id = _create_media(user_id)

        db = SessionLocal()
        try:
            first = attach_media_to_post(
                db,
                post_id=post_id,
                media_asset_id=first_asset_id,
                user_id=user_id,
                position=0,
            )
            second = attach_media_to_post(
                db,
                post_id=post_id,
                media_asset_id=second_asset_id,
                user_id=user_id,
                position=1,
            )

            assert first.position == 0
            assert second.position == 1

            rows = db.scalars(
                select(PostMedia)
                .where(PostMedia.post_id == post_id)
                .order_by(PostMedia.position)
            ).all()

            assert len(rows) == 2
            assert [row.media_asset_id for row in rows] == [
                first_asset_id,
                second_asset_id,
            ]
        finally:
            db.close()
    finally:
        _cleanup_user(user_id)
