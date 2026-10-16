from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SpaceCreateRequest(BaseModel):
    space_type: Literal["creator", "community", "organization"]
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=3, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    visibility: Literal["public", "private"] = "public"
    membership_policy: Literal["open", "approval"] = "open"

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Space name cannot be blank.")
        return value

    @field_validator("slug", mode="before")
    @classmethod
    def normalize_slug(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        import re

        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,78}[a-z0-9])", value):
            raise ValueError(
                "Slug must be 3–80 characters, use lowercase letters, "
                "numbers, and internal hyphens only."
            )
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class SpaceResponse(BaseModel):
    id: UUID
    owner_id: UUID
    space_type: Literal["creator", "community", "organization"]
    name: str
    slug: str
    description: str | None
    visibility: Literal["public", "private"]
    membership_policy: Literal["open", "approval"]
    created_at: datetime
    updated_at: datetime
    my_role: Literal["owner", "admin", "moderator", "member"] | None = None
    my_membership_status: Literal["active", "pending", "removed"] | None = None

    model_config = ConfigDict(extra="forbid")
