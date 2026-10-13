from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.profile import ProfileDiscoveryResponse


class FollowResponse(BaseModel):
    status: str

    model_config = ConfigDict(extra="forbid")


class FollowRequestResponse(BaseModel):
    id: UUID
    requester_id: UUID
    target_id: UUID
    status: str

    model_config = ConfigDict(from_attributes=True)


class FollowStatusResponse(BaseModel):
    status: Literal["none", "following", "pending"]

    model_config = ConfigDict(extra="forbid")


class SocialRelationshipCountsResponse(BaseModel):
    follower_count: int
    following_count: int

    model_config = ConfigDict(extra="forbid")


class FollowersResponse(BaseModel):
    items: list[ProfileDiscoveryResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")


class FollowingResponse(BaseModel):
    items: list[ProfileDiscoveryResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")
