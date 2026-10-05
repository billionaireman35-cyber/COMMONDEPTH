from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProfileCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    display_name: str | None = None
    avatar: str | None = None
    banner: str | None = None
    biography: str | None = None
    location: str | None = None
    visibility: str = "public"


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = None
    display_name: str | None = None
    avatar: str | None = None
    banner: str | None = None
    biography: str | None = None
    location: str | None = None
    visibility: str | None = None


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    display_name: str | None
    avatar: str | None
    banner: str | None
    biography: str | None
    location: str | None
    visibility: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ProfileDiscoveryResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    display_name: str | None
    avatar: str | None
    visibility: str

    model_config = ConfigDict(from_attributes=True)


class ProfileSearchItem(ProfileDiscoveryResponse):
    pass


class ProfileSearchResponse(BaseModel):
    items: list[ProfileSearchItem]
    next_cursor: str | None = None
