from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.messaging import Conversation, DirectMessage


class MessagingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _active_user(db: Session, user_id: UUID) -> User:
    user = db.scalar(
        select(User).where(
            User.id == user_id,
            User.status == "active",
            User.deleted_at.is_(None),
        )
    )
    if user is None:
        raise MessagingError("Account not found or unavailable.", 404)
    return user


def get_or_create_conversation(
    db: Session, current_user_id: UUID, recipient_id: UUID
) -> Conversation:
    if current_user_id == recipient_id:
        raise MessagingError("You cannot message yourself.")

    _active_user(db, current_user_id)
    _active_user(db, recipient_id)

    participant_one, participant_two = sorted(
        (current_user_id, recipient_id)
    )

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.participant_one_id == participant_one,
            Conversation.participant_two_id == participant_two,
        )
    )
    if conversation is not None:
        return conversation

    conversation = Conversation(
        participant_one_id=participant_one,
        participant_two_id=participant_two,
    )
    db.add(conversation)

    try:
        db.commit()
        db.refresh(conversation)
        return conversation
    except IntegrityError:
        db.rollback()
        conversation = db.scalar(
            select(Conversation).where(
                Conversation.participant_one_id == participant_one,
                Conversation.participant_two_id == participant_two,
            )
        )
        if conversation is not None:
            return conversation
        raise MessagingError("Could not create conversation. Please retry.", 409)


def get_conversation_for_participant(
    db: Session, conversation_id: UUID, user_id: UUID
) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            or_(
                Conversation.participant_one_id == user_id,
                Conversation.participant_two_id == user_id,
            ),
        )
    )
    if conversation is None:
        raise MessagingError("Conversation not found.", 404)
    return conversation


def list_conversations(
    db: Session, user_id: UUID, limit: int = 50
) -> list[Conversation]:
    _active_user(db, user_id)
    return list(
        db.scalars(
            select(Conversation)
            .where(
                or_(
                    Conversation.participant_one_id == user_id,
                    Conversation.participant_two_id == user_id,
                )
            )
            .order_by(
                Conversation.updated_at.desc(),
                Conversation.id.desc(),
            )
            .limit(min(max(limit, 1), 100))
        ).all()
    )


def list_messages(
    db: Session,
    conversation_id: UUID,
    user_id: UUID,
    limit: int = 50,
) -> list[DirectMessage]:
    get_conversation_for_participant(db, conversation_id, user_id)

    newest_first = list(
        db.scalars(
            select(DirectMessage)
            .where(
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.deleted_at.is_(None),
            )
            .order_by(
                DirectMessage.created_at.desc(),
                DirectMessage.id.desc(),
            )
            .limit(min(max(limit, 1), 100))
        ).all()
    )
    return list(reversed(newest_first))


def send_message(
    db: Session,
    conversation_id: UUID,
    sender_id: UUID,
    body: str,
) -> DirectMessage:
    _active_user(db, sender_id)
    get_conversation_for_participant(db, conversation_id, sender_id)

    clean_body = body.strip()
    if not clean_body:
        raise MessagingError("Message cannot be empty.")
    if len(clean_body) > 5000:
        raise MessagingError("Message exceeds 5000 characters.")

    message = DirectMessage(
        conversation_id=conversation_id,
        sender_id=sender_id,
        body=clean_body,
    )
    db.add(message)

    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise MessagingError("Conversation not found.", 404)

    conversation.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(message)
        return message
    except Exception:
        db.rollback()
        raise
