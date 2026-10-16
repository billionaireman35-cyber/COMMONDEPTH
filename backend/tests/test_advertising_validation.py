"""Non-database tests for advertising validation and security helpers."""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.advertising import (
    AdCampaignCreateRequest,
    AdCampaignUpdateRequest,
    AdReviewDecisionRequest,
)
from app.services import advertising_authorization
from app.services.advertising_fingerprints import (
    campaign_approval_is_current,
    campaign_content_fingerprint,
)


def valid_campaign_payload(**overrides):
    payload = {
        "name": "  Community launch  ",
        "primary_text": "  Discover our community.  ",
        "headline": "Join our community",
        "destination_url": "https://example.com/community",
        "target_topics": ["Technology", "technology", "Africa"],
        "budget_minor_units": 100_000,
        "daily_budget_minor_units": 10_000,
        "currency": "NGN",
    }
    payload.update(overrides)
    return payload


def test_create_schema_normalizes_text_and_duplicate_topics():
    campaign = AdCampaignCreateRequest(**valid_campaign_payload())

    assert campaign.name == "Community launch"
    assert campaign.primary_text == "Discover our community."
    assert campaign.target_topics == ["technology", "africa"]


@pytest.mark.parametrize(
    "destination",
    [
        "javascript:alert(1)",
        "//example.com/path",
        "https://user:password@example.com/path",
        "not-a-url",
        "ftp://example.com/file",
    ],
)
def test_create_schema_rejects_unsafe_or_invalid_destinations(destination):
    with pytest.raises(ValidationError):
        AdCampaignCreateRequest(
            **valid_campaign_payload(destination_url=destination)
        )


def test_create_schema_rejects_blank_required_text():
    with pytest.raises(ValidationError):
        AdCampaignCreateRequest(**valid_campaign_payload(name="   "))

    with pytest.raises(ValidationError):
        AdCampaignCreateRequest(
            **valid_campaign_payload(primary_text="   ")
        )


def test_create_schema_rejects_invalid_schedule():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        AdCampaignCreateRequest(
            **valid_campaign_payload(
                starts_at=now,
                ends_at=now - timedelta(minutes=1),
            )
        )



def test_schedule_helper_rejects_invalid_combined_schedule():
    from app.services.advertising_campaigns import (
        AdvertisingValidationError,
        _validate_campaign_schedule,
    )

    starts_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    ends_at = starts_at - timedelta(minutes=1)

    with pytest.raises(
        AdvertisingValidationError,
        match="ends_at must be later than starts_at",
    ):
        _validate_campaign_schedule(starts_at, ends_at)


def test_schedule_helper_accepts_open_ended_schedule():
    from app.services.advertising_campaigns import _validate_campaign_schedule

    starts_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    _validate_campaign_schedule(starts_at, None)


def test_schedule_helper_accepts_valid_combined_schedule():
    from app.services.advertising_campaigns import _validate_campaign_schedule

    starts_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    ends_at = starts_at + timedelta(days=7)
    _validate_campaign_schedule(starts_at, ends_at)


def test_update_schema_requires_at_least_one_field():
    with pytest.raises(ValidationError):
        AdCampaignUpdateRequest()


def test_update_schema_rejects_null_topics():
    with pytest.raises(ValidationError):
        AdCampaignUpdateRequest(target_topics=None)


def test_rejection_requires_a_nonblank_reason():
    with pytest.raises(ValidationError):
        AdReviewDecisionRequest(decision="reject", reason="   ")

    decision = AdReviewDecisionRequest(
        decision="reject",
        reason="  Destination requires additional review.  ",
    )
    assert decision.reason == "Destination requires additional review."


def test_approval_decision_does_not_require_a_rejection_reason():
    decision = AdReviewDecisionRequest(decision="approve")
    assert decision.decision == "approve"
    assert decision.reason is None


def fake_campaign(**overrides):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    values = {
        "organization_space_id": uuid4(),
        "name": "Community launch",
        "primary_text": "Discover our community.",
        "headline": "Join us",
        "destination_url": "https://example.com/community",
        "target_topics": json.dumps(
            ["technology", "africa"],
            separators=(",", ":"),
        ),
        "budget_minor_units": 100_000,
        "daily_budget_minor_units": 10_000,
        "currency": "NGN",
        "starts_at": now,
        "ends_at": now + timedelta(days=7),
        "approved_content_fingerprint": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_fingerprint_normalizes_json_topics_and_topic_lists():
    organization_space_id = uuid4()
    stored_json = fake_campaign(
        organization_space_id=organization_space_id,
        target_topics='["technology","africa"]',
    )
    equivalent_list = fake_campaign(
        organization_space_id=organization_space_id,
        target_topics=["technology", "africa"],
    )

    assert campaign_content_fingerprint(stored_json) == (
        campaign_content_fingerprint(equivalent_list)
    )


def test_fingerprint_normalizes_topic_case_and_duplicates():
    organization_space_id = uuid4()
    first = fake_campaign(
        organization_space_id=organization_space_id,
        target_topics='["Technology","Africa"]',
    )
    second = fake_campaign(
        organization_space_id=organization_space_id,
        target_topics='["technology","technology","AFRICA"]',
    )

    assert campaign_content_fingerprint(first) == (
        campaign_content_fingerprint(second)
    )


def test_fingerprint_changes_when_approved_content_changes():
    campaign = fake_campaign()
    campaign.approved_content_fingerprint = (
        campaign_content_fingerprint(campaign)
    )

    assert campaign_approval_is_current(campaign)

    campaign.primary_text = "A different advertising message."

    assert not campaign_approval_is_current(campaign)


def test_fingerprint_is_invalidated_by_budget_change():
    campaign = fake_campaign()
    campaign.approved_content_fingerprint = (
        campaign_content_fingerprint(campaign)
    )

    campaign.budget_minor_units += 1

    assert not campaign_approval_is_current(campaign)


def test_fingerprint_is_invalidated_by_topic_change():
    campaign = fake_campaign()
    campaign.approved_content_fingerprint = (
        campaign_content_fingerprint(campaign)
    )

    campaign.target_topics = '["technology","business"]'

    assert not campaign_approval_is_current(campaign)


@pytest.mark.parametrize(
    "configured_value",
    [
        "",
        "not-a-uuid",
        "123e4567-e89b-12d3-a456-426614174000,not-a-uuid",
        "123e4567-e89b-12d3-a456-426614174000,",
    ],
)
def test_invalid_reviewer_allowlist_fails_closed(
    monkeypatch,
    configured_value,
):
    monkeypatch.setattr(
        advertising_authorization,
        "get_settings",
        lambda: SimpleNamespace(
            advertising_reviewer_user_ids=configured_value
        ),
    )

    assert (
        advertising_authorization.configured_advertising_reviewer_ids()
        == frozenset()
    )


def test_configured_reviewer_allowlist_accepts_valid_uuids(monkeypatch):
    reviewer_id = uuid4()
    other_id = uuid4()

    monkeypatch.setattr(
        advertising_authorization,
        "get_settings",
        lambda: SimpleNamespace(
            advertising_reviewer_user_ids=f" {reviewer_id} , {other_id} "
        ),
    )

    assert advertising_authorization.configured_advertising_reviewer_ids() == (
        frozenset({reviewer_id, other_id})
    )
    assert advertising_authorization.is_configured_advertising_reviewer(
        reviewer_id
    )
    assert not advertising_authorization.is_configured_advertising_reviewer(
        uuid4()
    )


def test_malformed_stored_topics_cannot_pass_approval():
    campaign = fake_campaign(target_topics="not valid JSON")
    campaign.approved_content_fingerprint = "a" * 64

    assert not campaign_approval_is_current(campaign)


def test_fingerprint_rejects_malformed_stored_topics():
    campaign = fake_campaign(target_topics='["technology", null]')

    with pytest.raises(ValueError):
        campaign_content_fingerprint(campaign)
