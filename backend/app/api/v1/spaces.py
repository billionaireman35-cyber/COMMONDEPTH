from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.models.spaces import Space
from app.schemas.spaces import SpaceCreateRequest, SpaceResponse
from app.services.session_authentication import AuthenticatedSession
from app.services.spaces import (
    SpaceActorInactiveError,
    SpaceError,
    SpaceNotFoundError,
    SpaceSlugTakenError,
    create_space,
    get_space_for_user,
    get_user_membership,
    list_spaces_for_user,
)

router = APIRouter(prefix="/spaces", tags=["spaces"])


def _response(
    db: Session,
    space: Space,
    user_id,
) -> SpaceResponse:
    membership = get_user_membership(
        db,
        space_id=space.id,
        user_id=user_id,
    )
    return SpaceResponse(
        id=space.id,
        owner_id=space.owner_id,
        space_type=space.space_type,
        name=space.name,
        slug=space.slug,
        description=space.description,
        visibility=space.visibility,
        membership_policy=space.membership_policy,
        created_at=space.created_at,
        updated_at=space.updated_at,
        my_role=membership.role if membership else None,
        my_membership_status=membership.status if membership else None,
    )


def _raise_space_error(error: SpaceError) -> None:
    if isinstance(error, SpaceSlugTakenError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(error, SpaceActorInactiveError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(error, SpaceNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR

    raise HTTPException(
        status_code=code,
        detail=error.args[0] if error.args else "Space operation failed.",
    ) from error


@router.post(
    "",
    response_model=SpaceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_space_endpoint(
    payload: SpaceCreateRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> SpaceResponse:
    try:
        space = create_space(
            db,
            owner_id=session.user_id,
            space_type=payload.space_type,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            visibility=payload.visibility,
            membership_policy=payload.membership_policy,
        )
        return _response(db, space, session.user_id)
    except SpaceError as error:
        _raise_space_error(error)


@router.get("", response_model=list[SpaceResponse])
def my_spaces(
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> list[SpaceResponse]:
    spaces = list_spaces_for_user(db, user_id=session.user_id)
    return [
        _response(db, space, session.user_id)
        for space in spaces
    ]


@router.get("/{slug}", response_model=SpaceResponse)
def read_space(
    slug: str,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> SpaceResponse:
    try:
        space = get_space_for_user(
            db,
            user_id=session.user_id,
            slug=slug.strip().lower(),
        )
        return _response(db, space, session.user_id)
    except SpaceError as error:
        _raise_space_error(error)
