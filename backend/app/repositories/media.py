from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.media import MediaAsset, MediaUpload


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
