"""Validated request and response schemas for advertising campaigns."""

from datetime import datetime
from typing import Literal
from uuid import UUID
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class AdCampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    primary_text: str = Field(min_length=1, max_length=5000)
    headline: str | None = Field(default=None, max_length=160)
    destination_url: str = Field(min_length=1, max_length=2048)
    target_topics: list[str] = Field(default_factory=list, max_length=30)
    budget_minor_units: int = Field(gt=0, le=2_000_000_000)
    daily_budget_minor_units: int | None = Field(
        default=None,
        gt=0,
        le=2_000_000_000,
    )
    currency: str = Field(default="NGN", pattern=r"^[A-Z]{3}$")
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "primary_text")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("headline")
    @classmethod
    def normalize_headline(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("destination_url")
    @classmethod
    def validate_destination_url(cls, value: str) -> str:
        value = value.strip()
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme.lower() in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
            )
        except ValueError:
            valid = False

        if not valid:
            raise ValueError(
                "Destination must be an absolute HTTP or HTTPS URL "
                "without embedded credentials."
            )
        return value

    @field_validator("target_topics")
    @classmethod
    def normalize_topics(cls, value: list[str]) -> list[str]:
        normalized = []
        seen = set()

        for topic in value:
            topic = topic.strip().lower()
            if not topic:
                raise ValueError("Target topics cannot contain blank values.")
            if len(topic) > 80:
                raise ValueError("Each target topic must be at most 80 characters.")
            if topic not in seen:
                normalized.append(topic)
                seen.add(topic)

        return normalized

    @model_validator(mode="after")
    def validate_schedule(self):
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be later than starts_at.")
        return self


class AdCampaignUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    primary_text: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
    )
    headline: str | None = Field(default=None, max_length=160)
    destination_url: str | None = Field(
        default=None,
        min_length=1,
        max_length=2048,
    )
    target_topics: list[str] = Field(default_factory=list, max_length=30)
    budget_minor_units: int | None = Field(
        default=None,
        gt=0,
        le=2_000_000_000,
    )
    daily_budget_minor_units: int | None = Field(
        default=None,
        gt=0,
        le=2_000_000_000,
    )
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "primary_text")
    @classmethod
    def normalize_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("headline")
    @classmethod
    def normalize_optional_headline(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("destination_url")
    @classmethod
    def validate_optional_destination_url(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None
        return AdCampaignCreateRequest.validate_destination_url(value)

    @field_validator("target_topics")
    @classmethod
    def normalize_optional_topics(
        cls,
        value: list[str] | None,
    ) -> list[str] | None:
        if value is None:
            return None
        return AdCampaignCreateRequest.normalize_topics(value)

    @model_validator(mode="after")
    def validate_schedule(self):
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be later than starts_at.")
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied.")
        return self


class AdReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def require_rejection_reason(self):
        if self.decision == "reject" and not self.reason:
            raise ValueError("A reason is required when rejecting a campaign.")
        return self


class AdCampaignResponse(BaseModel):
    id: UUID
    organization_space_id: UUID
    created_by_user_id: UUID
    name: str
    status: Literal[
        "draft",
        "submitted",
        "under_review",
        "approved",
        "scheduled",
        "active",
        "completed",
        "rejected",
        "suspended",
        "cancelled",
    ]
    primary_text: str
    headline: str | None
    destination_url: str
    target_topics: list[str]
    budget_minor_units: int
    daily_budget_minor_units: int | None
    currency: str
    starts_at: datetime | None
    ends_at: datetime | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(extra="forbid")
