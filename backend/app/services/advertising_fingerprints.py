"""Deterministic fingerprints for approved advertising campaign content."""

import hashlib
import json
from datetime import datetime
from typing import Any


def _normalized_topics(value: Any) -> list[str]:
    """Normalize valid stored JSON text or topic lists; reject malformed data."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Stored advertising topics are invalid JSON.") from exc

    if not isinstance(value, list):
        raise ValueError("Stored advertising topics must be a list.")

    if any(not isinstance(topic, str) for topic in value):
        raise ValueError("Stored advertising topics must contain only strings.")

    normalized = []
    seen = set()

    for topic in value:
        topic = topic.strip().lower()
        if not topic or len(topic) > 80:
            raise ValueError("Stored advertising topic is invalid.")
        if topic not in seen:
            normalized.append(topic)
            seen.add(topic)

    return normalized


def campaign_content_fingerprint(campaign: Any) -> str:
    """Fingerprint delivery-relevant fields to detect stale approvals."""
    payload = {
        "organization_space_id": str(campaign.organization_space_id),
        "name": campaign.name,
        "primary_text": campaign.primary_text,
        "headline": campaign.headline,
        "destination_url": campaign.destination_url,
        "target_topics": _normalized_topics(campaign.target_topics),
        "budget_minor_units": campaign.budget_minor_units,
        "daily_budget_minor_units": campaign.daily_budget_minor_units,
        "currency": campaign.currency,
        "starts_at": (
            campaign.starts_at.isoformat()
            if isinstance(campaign.starts_at, datetime)
            else None
        ),
        "ends_at": (
            campaign.ends_at.isoformat()
            if isinstance(campaign.ends_at, datetime)
            else None
        ),
    }

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def campaign_approval_is_current(campaign: Any) -> bool:
    """True only when a stored approval fingerprint matches current content."""
    approved = campaign.approved_content_fingerprint
    if not approved:
        return False

    try:
        return approved == campaign_content_fingerprint(campaign)
    except (ValueError, TypeError, AttributeError):
        # Invalid stored content must never retain a valid approval.
        return False
