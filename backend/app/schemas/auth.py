from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DeviceRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str
    name: str | None = None
    device_identifier_hash: str | None = None


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    device: DeviceRegistrationRequest | None = None


class RegistrationResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    session_token: str
    session_expires_at: datetime


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    device: DeviceRegistrationRequest | None = None


class LoginResponse(BaseModel):
    user_id: UUID
    session_id: UUID
    session_token: str
    session_expires_at: datetime


class CurrentUserResponse(BaseModel):
    user_id: UUID
    status: str
