from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media import MediaAsset, MediaUpload, PostMedia


class MediaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_asset(self, asset_id: UUID) -> MediaAsset | None:
        statement = select(MediaAsset).where(MediaAsset.id == asset_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_upload(self, upload_id: UUID) -> MediaUpload | None:
        statement = select(MediaUpload).where(MediaUpload.id == upload_id)
        return self.db.execute(statement).scalar_one_or_none()

    def get_upload_by_asset_id(
        self,
        asset_id: UUID,
    ) -> MediaUpload | None:
        statement = select(MediaUpload).where(
            MediaUpload.media_asset_id == asset_id,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def add_asset(self, asset: MediaAsset) -> MediaAsset:
        self.db.add(asset)
        return asset

    def add_upload(self, upload: MediaUpload) -> MediaUpload:
        self.db.add(upload)
        return upload

    def get_post_media(
        self,
        *,
        post_id: UUID,
        media_asset_id: UUID,
    ) -> PostMedia | None:
        statement = select(PostMedia).where(
            PostMedia.post_id == post_id,
            PostMedia.media_asset_id == media_asset_id,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_post_media_by_position(
        self,
        *,
        post_id: UUID,
        position: int,
    ) -> PostMedia | None:
        statement = select(PostMedia).where(
            PostMedia.post_id == post_id,
            PostMedia.position == position,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_ready_media_by_post_ids(
        self,
        *,
        post_ids: list[UUID],
    ) -> dict[UUID, list[tuple[PostMedia, MediaAsset]]]:
        if not post_ids:
            return {}

        statement = (
            select(PostMedia, MediaAsset)
            .join(
                MediaAsset,
                MediaAsset.id == PostMedia.media_asset_id,
            )
            .where(
                PostMedia.post_id.in_(post_ids),
                MediaAsset.status == "ready",
                MediaAsset.deleted_at.is_(None),
            )
            .order_by(
                PostMedia.post_id.asc(),
                PostMedia.position.asc(),
                PostMedia.id.asc(),
            )
        )

        grouped: dict[UUID, list[tuple[PostMedia, MediaAsset]]] = {}

        for post_media, asset in self.db.execute(statement).all():
            grouped.setdefault(post_media.post_id, []).append(
                (post_media, asset)
            )

        return grouped

    def add_post_media(self, post_media: PostMedia) -> PostMedia:
        self.db.add(post_media)
        return post_media
