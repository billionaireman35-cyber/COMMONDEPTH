from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.spaces import Space, SpaceMembership


class SpaceError(Exception):
    """Base class for Space service errors."""


class SpaceActorInactiveError(SpaceError):
    """The actor is not an active user."""


class SpaceAccountTypePermissionError(SpaceError):
    """The account type cannot create the requested Space type."""


class SpaceSlugTakenError(SpaceError):
    """The requested Space slug is already in use."""


class SpaceNotFoundError(SpaceError):
    """The Space does not exist or is not visible to the actor."""


class SpacePersistenceError(SpaceError):
    """A Space operation could not be persisted."""


def create_space(
    db: Session,
    *,
    owner_id: UUID,
    space_type: str,
    name: str,
    slug: str,
    description: str | None,
    visibility: str,
    membership_policy: str,
) -> Space:
    owner = db.get(User, owner_id)
    if owner is None or owner.status != "active":
        raise SpaceActorInactiveError("An active account is required.")

    permitted_space_types = {
        "individual": {"community"},
        "creator": {"creator", "community"},
        "organization": {"organization", "community"},
    }
    if space_type not in permitted_space_types.get(owner.account_type, set()):
        raise SpaceAccountTypePermissionError(
            "Your account type is not permitted to create this Space type."
        )

    space = Space(
        owner_id=owner_id,
        space_type=space_type,
        name=name,
        slug=slug,
        description=description,
        visibility=visibility,
        membership_policy=membership_policy,
    )
    db.add(space)

    try:
        db.flush()
        db.add(
            SpaceMembership(
                space_id=space.id,
                user_id=owner_id,
                role="owner",
                status="active",
            )
        )
        db.flush()
        db.refresh(space)
        db.commit()
        return space
    except IntegrityError as error:
        constraint_name = getattr(
            getattr(error.orig, "diag", None),
            "constraint_name",
            None,
        )
        db.rollback()

        if constraint_name == "uq_spaces_slug":
            raise SpaceSlugTakenError(
                "That Space slug is already in use."
            ) from None

        raise SpacePersistenceError(
            "The Space could not be created."
        ) from None
    except Exception:
        db.rollback()
        raise SpacePersistenceError(
            "The Space could not be created."
        ) from None


def list_spaces_for_user(db: Session, *, user_id: UUID) -> list[Space]:
    membership_space_ids = select(SpaceMembership.space_id).where(
        SpaceMembership.user_id == user_id,
        SpaceMembership.status.in_(("active", "pending")),
    )

    statement = (
        select(Space)
        .where(
            or_(
                Space.owner_id == user_id,
                Space.id.in_(membership_space_ids),
            )
        )
        .order_by(Space.created_at.desc(), Space.id.desc())
    )
    return list(db.scalars(statement).all())


def get_space_for_user(
    db: Session,
    *,
    user_id: UUID,
    slug: str,
) -> Space:
    space = db.scalar(select(Space).where(Space.slug == slug))
    if space is None:
        raise SpaceNotFoundError("Space not found.")

    if space.visibility == "private" and space.owner_id != user_id:
        membership = db.scalar(
            select(SpaceMembership).where(
                SpaceMembership.space_id == space.id,
                SpaceMembership.user_id == user_id,
                SpaceMembership.status == "active",
            )
        )
        if membership is None:
            # Conceal private Space existence from unauthorized users.
            raise SpaceNotFoundError("Space not found.")

    return space


def get_user_membership(
    db: Session,
    *,
    space_id: UUID,
    user_id: UUID,
) -> SpaceMembership | None:
    return db.scalar(
        select(SpaceMembership).where(
            SpaceMembership.space_id == space_id,
            SpaceMembership.user_id == user_id,
        )
    )
