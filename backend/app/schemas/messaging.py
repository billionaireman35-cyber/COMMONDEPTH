from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreateRequest(BaseModel):
    recipient_id: UUID

    model_config = ConfigDict(extra="forbid")


class MessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=5000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("body")
    @classmethod
    def validate_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be empty.")
        return value.strip()


class DirectMessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_id: UUID
    body: str
    created_at: datetime
    edited_at: datetime | None

    model_config = ConfigDict(extra="forbid")


class ConversationParticipantResponse(BaseModel):
    user_id: UUID
    username: str
    display_name: str | None = None
    avatar: str | None = None

    model_config = ConfigDict(extra="forbid")


class ConversationResponse(BaseModel):
    id: UUID
    participant_one_id: UUID
    participant_two_id: UUID
    participant_one: ConversationParticipantResponse | None = None
    participant_two: ConversationParticipantResponse | None = None
    created_at: datetime
    updated_at: datetime
    latest_message: DirectMessageResponse | None = None

    model_config = ConfigDict(extra="forbid")


class ConversationHistoryResponse(BaseModel):
    conversation_id: UUID
    messages: list[DirectMessageResponse]

    model_config = ConfigDict(extra="forbid")
