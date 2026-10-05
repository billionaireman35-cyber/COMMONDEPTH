from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.profile import Profile
from app.models.social import Follow, FollowRequest
from app.repositories.profile import ProfileRepository
from app.repositories.social import SocialRepository


class SocialError(Exception):
    """Base class for social graph service errors."""


class SocialTargetNotFoundError(SocialError):
    """Raised when the requested target profile does not exist."""


class SocialTargetInactiveError(SocialError):
    """Raised when the target account is not active."""


class CannotFollowSelfError(SocialError):
    """Raised when a user attempts to follow themselves."""


class AlreadyFollowingError(SocialError):
    """Raised when an active follow already exists."""


class FollowRequestPendingError(SocialError):
    """Raised when a pending follow request already exists."""


class FollowRequestNotFoundError(SocialError):
    """Raised when a follow request does not exist."""


class FollowRequestUnauthorizedError(SocialError):
    """Raised when the authenticated user cannot act on a request."""


class InvalidFollowRequestStateError(SocialError):
    """Raised when a follow request is in an invalid state."""


def _get_target_profile(
    db: Session,
    *,
    username: str,
) -> Profile:
    from app.services.profile import normalize_username

    normalized_username = normalize_username(username)
    profile = ProfileRepository(db).get_by_username(normalized_username)

    if profile is None:
        raise SocialTargetNotFoundError("Profile not found.")

    return profile


def _get_active_target_user(
    db: Session,
    *,
    profile: Profile,
) -> User:
    user = db.get(User, profile.user_id)

    if user is None:
        raise SocialTargetNotFoundError("Profile not found.")

    if user.status != "active":
        raise SocialTargetInactiveError("User cannot be followed.")

    return user


def follow_user(
    db: Session,
    *,
    follower_id: UUID,
    username: str,
) -> Follow | FollowRequest:
    profile = _get_target_profile(db, username=username)
    target = _get_active_target_user(db, profile=profile)

    if follower_id == target.id:
        raise CannotFollowSelfError("You cannot follow yourself.")

    repository = SocialRepository(db)

    existing_follow = repository.get_follow(
        follower_id=follower_id,
        following_id=target.id,
    )
    if existing_follow is not None:
        raise AlreadyFollowingError("Already following this user.")

    existing_request = repository.get_follow_request(
        requester_id=follower_id,
        target_id=target.id,
    )

    if existing_request is not None:
        if existing_request.status == "pending":
            raise FollowRequestPendingError(
                "A follow request is already pending."
            )

        if existing_request.status == "rejected":
            existing_request.status = "pending"
            db.flush()
            db.commit()
            return existing_request

        raise InvalidFollowRequestStateError(
            "Follow request is in an invalid state."
        )

    if profile.visibility == "private":
        follow_request = FollowRequest(
            requester_id=follower_id,
            target_id=target.id,
            status="pending",
        )
        repository.add_follow_request(follow_request)

        try:
            db.flush()
            db.commit()
        except IntegrityError:
            db.rollback()

            existing_follow = repository.get_follow(
                follower_id=follower_id,
                following_id=target.id,
            )
            if existing_follow is not None:
                raise AlreadyFollowingError(
                    "Already following this user."
                ) from None

            existing_request = repository.get_follow_request(
                requester_id=follower_id,
                target_id=target.id,
            )
            if existing_request is not None:
                if existing_request.status == "pending":
                    raise FollowRequestPendingError(
                        "A follow request is already pending."
                    ) from None

            raise SocialError(
                "Follow request could not be created."
            ) from None

        return follow_request

    follow = Follow(
        follower_id=follower_id,
        following_id=target.id,
    )
    repository.add_follow(follow)

    try:
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()

        existing_follow = repository.get_follow(
            follower_id=follower_id,
            following_id=target.id,
        )
        if existing_follow is not None:
            raise AlreadyFollowingError(
                "Already following this user."
            ) from None

        raise SocialError(
            "Follow could not be created."
        ) from None

    return follow


def unfollow_user(
    db: Session,
    *,
    follower_id: UUID,
    username: str,
) -> None:
    profile = _get_target_profile(db, username=username)

    repository = SocialRepository(db)
    follow = repository.get_follow(
        follower_id=follower_id,
        following_id=profile.user_id,
    )

    if follow is None:
        raise FollowRequestNotFoundError(
            "Follow relationship does not exist."
        )

    repository.delete_follow(follow)
    db.commit()


def cancel_follow_by_username(
    db: Session,
    *,
    requester_user_id: UUID,
    username: str,
) -> None:
    profile = _get_target_profile(db, username=username)

    repository = SocialRepository(db)
    request = repository.get_follow_request(
        requester_id=requester_user_id,
        target_id=profile.user_id,
    )

    if request is None or request.status != "pending":
        raise FollowRequestNotFoundError(
            "Follow request does not exist."
        )

    repository.delete_follow_request(request)
    db.commit()

def _get_authorized_pending_request(
    db: Session,
    *,
    request_id: UUID,
    target_user_id: UUID,
) -> FollowRequest:
    repository = SocialRepository(db)
    request = repository.get_follow_request_by_id(request_id)

    if request is None:
        raise FollowRequestNotFoundError(
            "Follow request not found."
        )

    if request.target_id != target_user_id:
        raise FollowRequestUnauthorizedError(
            "You are not authorized to act on this follow request."
        )

    if request.status != "pending":
        raise InvalidFollowRequestStateError(
            "Follow request is no longer pending."
        )

    return request


def accept_follow_request(
    db: Session,
    *,
    target_user_id: UUID,
    request_id: UUID,
) -> Follow:
    request = _get_authorized_pending_request(
        db,
        request_id=request_id,
        target_user_id=target_user_id,
    )

    repository = SocialRepository(db)

    existing_follow = repository.get_follow(
        follower_id=request.requester_id,
        following_id=request.target_id,
    )
    if existing_follow is not None:
        repository.delete_follow_request(request)
        db.commit()
        return existing_follow

    follow = Follow(
        follower_id=request.requester_id,
        following_id=request.target_id,
    )
    repository.add_follow(follow)
    repository.delete_follow_request(request)

    try:
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SocialError(
            "Follow request could not be accepted."
        ) from None

    return follow


def reject_follow_request(
    db: Session,
    *,
    target_user_id: UUID,
    request_id: UUID,
) -> FollowRequest:
    request = _get_authorized_pending_request(
        db,
        request_id=request_id,
        target_user_id=target_user_id,
    )

    request.status = "rejected"

    try:
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SocialError(
            "Follow request could not be rejected."
        ) from None

    return request


def cancel_follow_request(
    db: Session,
    *,
    requester_user_id: UUID,
    request_id: UUID,
) -> None:
    repository = SocialRepository(db)
    request = repository.get_follow_request_by_id(request_id)

    if request is None:
        raise FollowRequestNotFoundError(
            "Follow request not found."
        )

    if request.requester_id != requester_user_id:
        raise FollowRequestUnauthorizedError(
            "You are not authorized to cancel this follow request."
        )

    if request.status != "pending":
        raise InvalidFollowRequestStateError(
            "Follow request is no longer pending."
        )

    repository.delete_follow_request(request)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SocialError(
            "Follow request could not be cancelled."
        ) from None
