from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FollowResponse(BaseModel):
    status: str

    model_config = ConfigDict(extra="forbid")


class FollowRequestResponse(BaseModel):
    id: UUID
    requester_id: UUID
    target_id: UUID
    status: str

    model_config = ConfigDict(from_attributes=True)
