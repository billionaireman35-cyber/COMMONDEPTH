from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session, get_media_storage
from app.core.database import get_db
from app.schemas.profile import ProfileSearchItem
from app.services.onboarding import get_curated_follow_suggestions
from app.services.profile_media import serialize_profile_discovery_response
from app.integrations.media_storage.protocol import MediaStorage
from app.services.session_authentication import AuthenticatedSession


router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get(
    "/follow-suggestions",
    response_model=list[ProfileSearchItem],
)
def get_follow_suggestions(
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
) -> list[ProfileSearchItem]:
    profiles = get_curated_follow_suggestions(
        db,
        viewer_user_id=authenticated.user_id,
    )

    return [
        ProfileSearchItem.model_validate(
            serialize_profile_discovery_response(
                db,
                profile,
                storage=storage,
            )
        )
        for profile in profiles
    ]
