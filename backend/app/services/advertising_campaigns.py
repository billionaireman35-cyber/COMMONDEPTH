"""Organization-owned advertising campaign management and review."""

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.advertising import AdCampaign, AdReviewEvent
from app.models.identity import User
from app.models.spaces import Space
from app.schemas.advertising import (
    AdCampaignCreateRequest,
    AdCampaignUpdateRequest,
)
from app.services.advertising_authorization import (
    is_configured_advertising_reviewer,
)
from app.services.advertising_fingerprints import (
    campaign_content_fingerprint,
)


class AdvertisingError(Exception):
    """Base class for advertising workflow errors."""


class AdvertisingNotFoundError(AdvertisingError):
    """A campaign or eligible organization Space was not found."""


class AdvertisingPermissionError(AdvertisingError):
    """The actor is not permitted to perform this operation."""


class AdvertisingConflictError(AdvertisingError):
    """The campaign is in a state that disallows this operation."""


class AdvertisingValidationError(AdvertisingError):
    """The combined campaign data is invalid."""


class AdvertisingPersistenceError(AdvertisingError):
    """The operation could not be persisted."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _active_user(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise AdvertisingPermissionError("An active account is required.")
    return user


def _owned_organization_space(
    db: Session,
    *,
    space_id: UUID,
    owner_id: UUID,
) -> Space:
    space = db.get(Space, space_id)

    if space is None or space.space_type != "organization":
        raise AdvertisingNotFoundError("Organization Space not found.")

    if space.owner_id != owner_id:
        raise AdvertisingPermissionError(
            "Only the Organization Space owner can manage its campaigns."
        )

    owner = _active_user(db, owner_id)
    if owner.account_type != "organization":
        raise AdvertisingPermissionError(
            "An organization account is required to advertise."
        )

    return space


def _get_owned_campaign(
    db: Session,
    *,
    campaign_id: UUID,
    owner_id: UUID,
) -> AdCampaign:
    campaign = db.get(AdCampaign, campaign_id)

    if campaign is None:
        raise AdvertisingNotFoundError("Campaign not found.")

    _owned_organization_space(
        db,
        space_id=campaign.organization_space_id,
        owner_id=owner_id,
    )
    return campaign


def _topics_to_storage(topics: list[str]) -> str:
    """Store topics as canonical JSON in the existing TEXT column."""
    return json.dumps(
        topics,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _write_event(
    db: Session,
    *,
    campaign: AdCampaign,
    actor_id: UUID,
    event_type: str,
    previous_status: str | None,
    resulting_status: str | None,
    reason: str | None = None,
) -> None:
    db.add(
        AdReviewEvent(
            campaign_id=campaign.id,
            actor_user_id=actor_id,
            event_type=event_type,
            previous_status=previous_status,
            resulting_status=resulting_status,
            reason=reason,
        )
    )


def _persist(db: Session) -> None:
    try:
        db.flush()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise AdvertisingPersistenceError(
            "The advertising operation could not be saved."
        ) from None


def list_campaigns_for_space(
    db: Session,
    *,
    space_id: UUID,
    owner_id: UUID,
) -> list[AdCampaign]:
    _owned_organization_space(
        db,
        space_id=space_id,
        owner_id=owner_id,
    )

    statement = (
        select(AdCampaign)
        .where(AdCampaign.organization_space_id == space_id)
        .order_by(AdCampaign.created_at.desc(), AdCampaign.id.desc())
    )
    return list(db.scalars(statement).all())


def get_campaign_for_owner(
    db: Session,
    *,
    campaign_id: UUID,
    owner_id: UUID,
) -> AdCampaign:
    _active_user(db, owner_id)
    return _get_owned_campaign(
        db,
        campaign_id=campaign_id,
        owner_id=owner_id,
    )


def create_campaign(
    db: Session,
    *,
    owner_id: UUID,
    space_id: UUID,
    payload: AdCampaignCreateRequest,
) -> AdCampaign:
    _owned_organization_space(
        db,
        space_id=space_id,
        owner_id=owner_id,
    )

    campaign = AdCampaign(
        organization_space_id=space_id,
        created_by_user_id=owner_id,
        name=payload.name,
        status="draft",
        primary_text=payload.primary_text,
        headline=payload.headline,
        destination_url=payload.destination_url,
        target_topics=_topics_to_storage(payload.target_topics),
        budget_minor_units=payload.budget_minor_units,
        daily_budget_minor_units=payload.daily_budget_minor_units,
        currency=payload.currency,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
    )

    try:
        db.add(campaign)
        db.flush()

        _write_event(
            db,
            campaign=campaign,
            actor_id=owner_id,
            event_type="created",
            previous_status=None,
            resulting_status="draft",
        )
        db.flush()
        db.refresh(campaign)
        db.commit()
        return campaign
    except SQLAlchemyError:
        db.rollback()
        raise AdvertisingPersistenceError(
            "The campaign could not be created."
        ) from None



def _validate_campaign_schedule(
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> None:
    """Validate a combined schedule without mutating ORM state."""
    if starts_at is not None and ends_at is not None and ends_at <= starts_at:
        raise AdvertisingValidationError(
            "ends_at must be later than starts_at."
        )


def update_campaign(
    db: Session,
    *,
    campaign_id: UUID,
    owner_id: UUID,
    payload: AdCampaignUpdateRequest,
) -> AdCampaign:
    _active_user(db, owner_id)
    campaign = _get_owned_campaign(
        db,
        campaign_id=campaign_id,
        owner_id=owner_id,
    )

    if campaign.status not in {"draft", "rejected"}:
        raise AdvertisingConflictError(
            "Only draft or rejected campaigns can be edited."
        )

    changes = payload.model_dump(exclude_unset=True)
    previous_status = campaign.status

    for field in (
        "name",
        "primary_text",
        "destination_url",
        "budget_minor_units",
        "currency",
    ):
        if field in changes and changes[field] is None:
            raise AdvertisingValidationError(f"{field} cannot be null.")

    if "target_topics" in changes and changes["target_topics"] is None:
        raise AdvertisingValidationError("target_topics cannot be null.")

    # Validate the proposed combined schedule before changing the ORM object.
    _validate_campaign_schedule(
        changes.get("starts_at", campaign.starts_at),
        changes.get("ends_at", campaign.ends_at),
    )

    # Prepare serialization before applying any ORM mutations.
    serialized_topics = (
        _topics_to_storage(changes["target_topics"])
        if "target_topics" in changes
        else None
    )

    for field in (
        "name",
        "primary_text",
        "headline",
        "destination_url",
        "budget_minor_units",
        "daily_budget_minor_units",
        "currency",
        "starts_at",
        "ends_at",
    ):
        if field in changes:
            setattr(campaign, field, changes[field])

    if serialized_topics is not None:
        campaign.target_topics = serialized_topics

    campaign.status = "draft"
    campaign.approved_content_fingerprint = None
    campaign.reviewed_at = None
    campaign.submitted_at = None
    campaign.updated_at = _now()

    _write_event(
        db,
        campaign=campaign,
        actor_id=owner_id,
        event_type="edited",
        previous_status=previous_status,
        resulting_status="draft",
        reason="Campaign content or settings updated.",
    )

    _persist(db)
    db.refresh(campaign)
    return campaign


def submit_campaign(
    db: Session,
    *,
    campaign_id: UUID,
    owner_id: UUID,
) -> AdCampaign:
    _active_user(db, owner_id)
    campaign = _get_owned_campaign(
        db,
        campaign_id=campaign_id,
        owner_id=owner_id,
    )

    if campaign.status not in {"draft", "rejected"}:
        raise AdvertisingConflictError(
            "Only draft or rejected campaigns can be submitted."
        )

    _validate_campaign_schedule(campaign.starts_at, campaign.ends_at)

    previous_status = campaign.status
    campaign.status = "submitted"
    campaign.submitted_at = _now()
    campaign.reviewed_at = None
    campaign.approved_content_fingerprint = None
    campaign.updated_at = _now()

    _write_event(
        db,
        campaign=campaign,
        actor_id=owner_id,
        event_type="submitted",
        previous_status=previous_status,
        resulting_status="submitted",
    )

    _persist(db)
    db.refresh(campaign)
    return campaign


def review_campaign(
    db: Session,
    *,
    campaign_id: UUID,
    reviewer_id: UUID,
    decision: str,
    reason: str | None = None,
) -> AdCampaign:
    reviewer = _active_user(db, reviewer_id)

    if not is_configured_advertising_reviewer(reviewer.id):
        raise AdvertisingPermissionError(
            "You are not authorized to review advertising campaigns."
        )

    if decision not in {"approve", "reject"}:
        raise AdvertisingValidationError("Invalid review decision.")

    if decision == "reject" and not (reason and reason.strip()):
        raise AdvertisingValidationError(
            "A reason is required when rejecting a campaign."
        )

    # Lock the campaign row before checking its review state. Concurrent
    # reviewers must wait and then check the latest committed status.
    campaign = db.scalar(
        select(AdCampaign)
        .where(AdCampaign.id == campaign_id)
        .with_for_update()
    )
    if campaign is None:
        raise AdvertisingNotFoundError("Campaign not found.")

    space = db.get(Space, campaign.organization_space_id)
    if space is None or space.space_type != "organization":
        raise AdvertisingNotFoundError("Organization Space not found.")

    # Advertisers cannot review their own campaigns.
    if reviewer_id in {campaign.created_by_user_id, space.owner_id}:
        raise AdvertisingPermissionError(
            "Advertisers cannot review their own campaigns."
        )

    # Crucially, check the state after acquiring the row lock.
    if campaign.status not in {"submitted", "under_review"}:
        raise AdvertisingConflictError(
            "Only submitted campaigns can be reviewed."
        )

    previous_status = campaign.status
    now = _now()

    if previous_status == "submitted":
        campaign.status = "under_review"
        _write_event(
            db,
            campaign=campaign,
            actor_id=reviewer_id,
            event_type="review_started",
            previous_status="submitted",
            resulting_status="under_review",
        )

    if decision == "approve":
        campaign.status = "approved"
        campaign.approved_content_fingerprint = (
            campaign_content_fingerprint(campaign)
        )
        event_type = "approved"
    else:
        campaign.status = "rejected"
        campaign.approved_content_fingerprint = None
        event_type = "rejected"

    campaign.reviewed_at = now
    campaign.updated_at = now

    _write_event(
        db,
        campaign=campaign,
        actor_id=reviewer_id,
        event_type=event_type,
        previous_status="under_review",
        resulting_status=campaign.status,
        reason=reason.strip() if reason else None,
    )

    # Persist the transition and its audit events together.
    _persist(db)
    db.refresh(campaign)
    return campaign
