from unittest.mock import patch

import pytest

from app.services.google_oidc import (
    GOOGLE_AUTHENTICATION_FAILED_MESSAGE,
    GoogleOIDCError,
    GoogleIdentityClaims,
    verify_google_id_token,
)


def _claims(**overrides):
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "google-sub-123",
        "aud": "google-client-id",
        "exp": 4102444800,
        "email": "user@example.com",
        "email_verified": True,
    }
    claims.update(overrides)
    return claims


def test_valid_google_id_token_returns_identity_claims() -> None:
    with patch(
        "app.services.google_oidc.id_token.verify_oauth2_token",
        return_value=_claims(),
    ):
        result = verify_google_id_token(
            "valid-google-token",
            client_id="google-client-id",
        )

    assert isinstance(result, GoogleIdentityClaims)
    assert result.subject == "google-sub-123"
    assert result.email == "user@example.com"
    assert result.email_verified is True


def test_missing_client_id_is_rejected() -> None:
    with pytest.raises(GoogleOIDCError) as exc_info:
        verify_google_id_token(
            "valid-google-token",
            client_id=None,
        )

    assert str(exc_info.value) == GOOGLE_AUTHENTICATION_FAILED_MESSAGE


def test_empty_token_is_rejected() -> None:
    with pytest.raises(GoogleOIDCError) as exc_info:
        verify_google_id_token(
            "",
            client_id="google-client-id",
        )

    assert str(exc_info.value) == GOOGLE_AUTHENTICATION_FAILED_MESSAGE


def test_invalid_google_token_is_rejected() -> None:
    with patch(
        "app.services.google_oidc.id_token.verify_oauth2_token",
        side_effect=ValueError("invalid token"),
    ):
        with pytest.raises(GoogleOIDCError) as exc_info:
            verify_google_id_token(
                "invalid-token",
                client_id="google-client-id",
            )

    assert str(exc_info.value) == GOOGLE_AUTHENTICATION_FAILED_MESSAGE


def test_wrong_issuer_is_rejected() -> None:
    with patch(
        "app.services.google_oidc.id_token.verify_oauth2_token",
        return_value=_claims(iss="https://attacker.example"),
    ):
        with pytest.raises(GoogleOIDCError) as exc_info:
            verify_google_id_token(
                "valid-google-token",
                client_id="google-client-id",
            )

    assert str(exc_info.value) == GOOGLE_AUTHENTICATION_FAILED_MESSAGE


def test_missing_subject_is_rejected() -> None:
    with patch(
        "app.services.google_oidc.id_token.verify_oauth2_token",
        return_value=_claims(sub=None),
    ):
        with pytest.raises(GoogleOIDCError) as exc_info:
            verify_google_id_token(
                "valid-google-token",
                client_id="google-client-id",
            )

    assert str(exc_info.value) == GOOGLE_AUTHENTICATION_FAILED_MESSAGE


def test_google_verifier_receives_configured_client_id() -> None:
    with patch(
        "app.services.google_oidc.id_token.verify_oauth2_token",
        return_value=_claims(),
    ) as verifier:
        verify_google_id_token(
            "valid-google-token",
            client_id="expected-google-client-id",
        )

    verifier.assert_called_once()
    assert verifier.call_args.kwargs["audience"] == "expected-google-client-id"
