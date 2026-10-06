from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostCreateRequest(BaseModel):
    content: str = Field(max_length=5000)
    visibility: Literal["public", "followers"] = "public"

    model_config = ConfigDict(extra="forbid")


class PostResponse(BaseModel):
    id: UUID
    author_id: UUID
    content: str
    visibility: Literal["public", "followers"]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    items: list[PostResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")
