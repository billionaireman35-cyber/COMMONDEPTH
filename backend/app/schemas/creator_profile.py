from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreatorProfileSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profession: str = Field(min_length=1, max_length=120)
    niche: str = Field(min_length=1, max_length=120)
    content_types: list[str] = Field(min_length=1, max_length=12)
    introduction: str = Field(min_length=1, max_length=3000)

    @field_validator("profession", "niche", "introduction")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("content_types")
    @classmethod
    def normalize_content_types(cls, values: list[str]) -> list[str]:
        allowed = {
            "articles",
            "videos",
            "photography",
            "podcasts",
            "livestreams",
            "educational",
            "reviews",
            "art",
            "music",
            "other",
        }

        normalized: list[str] = []
        for value in values:
            item = value.strip().lower()
            if item not in allowed:
                raise ValueError(
                    "One or more content types are not supported."
                )
            if item not in normalized:
                normalized.append(item)

        if not normalized:
            raise ValueError("Choose at least one content type.")

        return normalized


class CreatorProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    profession: str
    niche: str
    content_types: list[str]
    introduction: str
    created_at: datetime
    updated_at: datetime

    account_type: Literal["creator"] = "creator"

    model_config = ConfigDict(from_attributes=True)
