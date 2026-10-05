from dataclasses import dataclass

from google.auth import exceptions as google_auth_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_AUTHENTICATION_FAILED_MESSAGE = "Authentication failed."


class GoogleOIDCError(Exception):
    """Raised when a Google ID token cannot be authenticated."""


@dataclass(frozen=True)
class GoogleIdentityClaims:
    subject: str
    email: str | None
    email_verified: bool | None


def verify_google_id_token(
    token: str,
    *,
    client_id: str | None,
) -> GoogleIdentityClaims:
    if not isinstance(token, str) or not token.strip():
        raise GoogleOIDCError(GOOGLE_AUTHENTICATION_FAILED_MESSAGE)

    if not isinstance(client_id, str) or not client_id.strip():
        raise GoogleOIDCError(GOOGLE_AUTHENTICATION_FAILED_MESSAGE)

    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=client_id,
        )
    except (
        ValueError,
        google_auth_exceptions.GoogleAuthError,
        google_auth_exceptions.TransportError,
    ):
        raise GoogleOIDCError(
            GOOGLE_AUTHENTICATION_FAILED_MESSAGE
        ) from None
    except Exception:
        raise GoogleOIDCError(
            GOOGLE_AUTHENTICATION_FAILED_MESSAGE
        ) from None

    issuer = claims.get("iss")
    subject = claims.get("sub")

    if issuer not in {
        GOOGLE_ISSUER,
        "accounts.google.com",
    }:
        raise GoogleOIDCError(GOOGLE_AUTHENTICATION_FAILED_MESSAGE)

    if not isinstance(subject, str) or not subject:
        raise GoogleOIDCError(GOOGLE_AUTHENTICATION_FAILED_MESSAGE)

    email = claims.get("email")
    if email is not None and not isinstance(email, str):
        email = None

    email_verified = claims.get("email_verified")
    if email_verified is not None and not isinstance(email_verified, bool):
        email_verified = None

    return GoogleIdentityClaims(
        subject=subject,
        email=email,
        email_verified=email_verified,
    )
