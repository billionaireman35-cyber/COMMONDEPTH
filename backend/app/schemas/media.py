from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MediaUploadCreateRequest(BaseModel):
    media_type: str = Field(min_length=1, max_length=16)
    mime_type: str = Field(min_length=1, max_length=128)
    file_size: int = Field(gt=0)

    model_config = ConfigDict(extra="forbid")


class MediaUploadCreateResponse(BaseModel):
    asset_id: UUID
    upload_id: UUID
    storage_provider: str
    storage_key: str
    upload_url: str
    expires_at: datetime

    model_config = ConfigDict(extra="forbid")



class MediaUploadCompleteResponse(BaseModel):
    asset_id: UUID
    upload_id: UUID
    upload_status: str
    asset_status: str
    completed_at: datetime

    model_config = ConfigDict(extra="forbid")


class PostMediaAttachRequest(BaseModel):
    media_asset_id: UUID
    position: int = Field(ge=0)

    model_config = ConfigDict(extra="forbid")


class PostMediaResponse(BaseModel):
    id: UUID
    post_id: UUID
    media_asset_id: UUID
    position: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
