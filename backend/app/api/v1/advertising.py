"""Authenticated advertising campaign management and moderation API."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.models.advertising import AdCampaign
from app.schemas.advertising import (
    AdCampaignCreateRequest,
    AdCampaignResponse,
    AdCampaignUpdateRequest,
    AdReviewDecisionRequest,
)
from app.services.advertising_campaigns import (
    AdvertisingConflictError,
    AdvertisingError,
    AdvertisingNotFoundError,
    AdvertisingPermissionError,
    AdvertisingPersistenceError,
    AdvertisingValidationError,
    create_campaign,
    get_campaign_for_owner,
    list_campaigns_for_space,
    review_campaign,
    submit_campaign,
    update_campaign,
)
from app.services.session_authentication import AuthenticatedSession

router = APIRouter(prefix="/advertising", tags=["advertising"])


def _response(campaign: AdCampaign) -> AdCampaignResponse:
    """Convert the internal TEXT representation into the public schema."""
    try:
        topics = json.loads(campaign.target_topics)
    except (json.JSONDecodeError, TypeError):
        topics = None

    # Do not expose malformed stored data as an arbitrary response shape.
    if not isinstance(topics, list) or any(
        not isinstance(topic, str) for topic in topics
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Campaign data could not be read.",
        )

    return AdCampaignResponse(
        id=campaign.id,
        organization_space_id=campaign.organization_space_id,
        created_by_user_id=campaign.created_by_user_id,
        name=campaign.name,
        status=campaign.status,
        primary_text=campaign.primary_text,
        headline=campaign.headline,
        destination_url=campaign.destination_url,
        target_topics=topics,
        budget_minor_units=campaign.budget_minor_units,
        daily_budget_minor_units=campaign.daily_budget_minor_units,
        currency=campaign.currency,
        starts_at=campaign.starts_at,
        ends_at=campaign.ends_at,
        submitted_at=campaign.submitted_at,
        reviewed_at=campaign.reviewed_at,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def _raise_advertising_error(error: AdvertisingError) -> None:
    if isinstance(error, AdvertisingNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(error, AdvertisingPermissionError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, AdvertisingConflictError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, AdvertisingValidationError):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(error, AdvertisingPersistenceError):
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR

    # Known service errors contain safe, intentional messages.
    detail = (
        error.args[0]
        if error.args and code != status.HTTP_500_INTERNAL_SERVER_ERROR
        else "The advertising operation could not be completed."
    )
    raise HTTPException(status_code=code, detail=detail) from error


@router.post(
    "/spaces/{space_id}/campaigns",
    response_model=AdCampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign_endpoint(
    space_id: UUID,
    payload: AdCampaignCreateRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> AdCampaignResponse:
    try:
        campaign = create_campaign(
            db,
            owner_id=session.user_id,
            space_id=space_id,
            payload=payload,
        )
        return _response(campaign)
    except AdvertisingError as error:
        _raise_advertising_error(error)


@router.get(
    "/spaces/{space_id}/campaigns",
    response_model=list[AdCampaignResponse],
)
def list_campaigns_endpoint(
    space_id: UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> list[AdCampaignResponse]:
    try:
        campaigns = list_campaigns_for_space(
            db,
            space_id=space_id,
            owner_id=session.user_id,
        )
        return [_response(campaign) for campaign in campaigns]
    except AdvertisingError as error:
        _raise_advertising_error(error)


@router.get(
    "/campaigns/{campaign_id}",
    response_model=AdCampaignResponse,
)
def get_campaign_endpoint(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> AdCampaignResponse:
    try:
        campaign = get_campaign_for_owner(
            db,
            campaign_id=campaign_id,
            owner_id=session.user_id,
        )
        return _response(campaign)
    except AdvertisingError as error:
        _raise_advertising_error(error)


@router.patch(
    "/campaigns/{campaign_id}",
    response_model=AdCampaignResponse,
)
def update_campaign_endpoint(
    campaign_id: UUID,
    payload: AdCampaignUpdateRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> AdCampaignResponse:
    try:
        campaign = update_campaign(
            db,
            campaign_id=campaign_id,
            owner_id=session.user_id,
            payload=payload,
        )
        return _response(campaign)
    except AdvertisingError as error:
        _raise_advertising_error(error)


@router.post(
    "/campaigns/{campaign_id}/submit",
    response_model=AdCampaignResponse,
)
def submit_campaign_endpoint(
    campaign_id: UUID,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> AdCampaignResponse:
    try:
        campaign = submit_campaign(
            db,
            campaign_id=campaign_id,
            owner_id=session.user_id,
        )
        return _response(campaign)
    except AdvertisingError as error:
        _raise_advertising_error(error)


@router.post(
    "/review/campaigns/{campaign_id}",
    response_model=AdCampaignResponse,
)
def review_campaign_endpoint(
    campaign_id: UUID,
    payload: AdReviewDecisionRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> AdCampaignResponse:
    try:
        campaign = review_campaign(
            db,
            campaign_id=campaign_id,
            reviewer_id=session.user_id,
            decision=payload.decision,
            reason=payload.reason,
        )
        return _response(campaign)
    except AdvertisingError as error:
        _raise_advertising_error(error)
