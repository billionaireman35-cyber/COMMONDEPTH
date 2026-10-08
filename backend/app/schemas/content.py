from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostCreateRequest(BaseModel):
    content: str = Field(max_length=5000)
    visibility: Literal["public", "followers"] = "public"

    model_config = ConfigDict(extra="forbid")


class PostMediaReadResponse(BaseModel):
    id: UUID
    media_asset_id: UUID
    media_type: str
    mime_type: str
    file_size: int
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    url: str
    position: int

    model_config = ConfigDict(extra="forbid")


class PostResponse(BaseModel):
    id: UUID
    author_id: UUID
    content: str
    visibility: Literal["public", "followers"]
    created_at: datetime
    updated_at: datetime
    like_count: int
    comment_count: int
    viewer_has_liked: bool
    media: list[PostMediaReadResponse]

    model_config = ConfigDict(from_attributes=True)


class PostCommentCreateRequest(BaseModel):
    content: str = Field(max_length=1000)

    model_config = ConfigDict(extra="forbid")


class PostCommentResponse(BaseModel):
    id: UUID
    post_id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostCommentListResponse(BaseModel):
    items: list[PostCommentResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")


class PostLikeResponse(BaseModel):
    liked: bool
    like_count: int

    model_config = ConfigDict(extra="forbid")


class PostListResponse(BaseModel):
    items: list[PostResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")
