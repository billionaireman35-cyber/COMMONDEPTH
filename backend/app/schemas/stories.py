from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StoryCreateRequest(BaseModel):
    visibility: Literal["public", "followers"] = "public"
    text_content: str | None = Field(default=None, max_length=5000)
    media_asset_ids: list[UUID] = Field(default_factory=list, max_length=10)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_content(self):
        if not (self.text_content and self.text_content.strip()) and not self.media_asset_ids:
            raise ValueError("A Story must contain text or at least one media item.")
        if len(set(self.media_asset_ids)) != len(self.media_asset_ids):
            raise ValueError("Duplicate Story media is not allowed.")
        return self


class StoryMediaResponse(BaseModel):
    id: UUID
    media_asset_id: UUID
    media_type: Literal['image', 'video']
    position: int
    media_url: str

    model_config = ConfigDict(extra="forbid")


class StoryResponse(BaseModel):
    id: UUID
    author_id: UUID
    author_username: str
    visibility: Literal["public", "followers"]
    text_content: str | None
    expires_at: datetime
    created_at: datetime
    media: list[StoryMediaResponse] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")
