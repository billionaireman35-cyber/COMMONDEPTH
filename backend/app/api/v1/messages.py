from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_authenticated_session
from app.core.database import get_db
from app.models.messaging import Conversation, DirectMessage
from app.models.profile import Profile
from app.services.messaging import (
    MessagingError,
    get_conversation_for_participant,
    get_or_create_conversation,
    list_conversations,
    list_messages,
    send_message,
)
from app.services.session_authentication import AuthenticatedSession
from app.schemas.messaging import (
    ConversationCreateRequest,
    ConversationHistoryResponse,
    ConversationParticipantResponse,
    ConversationResponse,
    DirectMessageResponse,
    MessageCreateRequest,
)

router = APIRouter(prefix="/messages", tags=["messages"])


def _message_response(message: DirectMessage) -> DirectMessageResponse:
    return DirectMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        body=message.body,
        created_at=message.created_at,
        edited_at=message.edited_at,
    )


def _participant_identity(db: Session, user_id) -> ConversationParticipantResponse | None:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        return None
    return ConversationParticipantResponse(
        user_id=profile.user_id,
        username=profile.username,
        display_name=profile.display_name,
        avatar=profile.avatar,
    )


def _conversation_response(
    db: Session, conversation: Conversation
) -> ConversationResponse:
    latest = db.scalar(
        select(DirectMessage)
        .where(
            DirectMessage.conversation_id == conversation.id,
            DirectMessage.deleted_at.is_(None),
        )
        .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
        .limit(1)
    )
    return ConversationResponse(
        id=conversation.id,
        participant_one_id=conversation.participant_one_id,
        participant_two_id=conversation.participant_two_id,
        participant_one=_participant_identity(db, conversation.participant_one_id),
        participant_two=_participant_identity(db, conversation.participant_two_id),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        latest_message=_message_response(latest) if latest else None,
    )


def _raise_messaging_error(error: MessagingError) -> None:
    raise HTTPException(
        status_code=error.status_code,
        detail=error.message,
    ) from error


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> ConversationResponse:
    try:
        conversation = get_or_create_conversation(
            db, session.user_id, payload.recipient_id
        )
        return _conversation_response(db, conversation)
    except MessagingError as error:
        _raise_messaging_error(error)


@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
)
def inbox(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> list[ConversationResponse]:
    try:
        conversations = list_conversations(db, session.user_id, limit)
        return [
            _conversation_response(db, conversation)
            for conversation in conversations
        ]
    except MessagingError as error:
        _raise_messaging_error(error)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationHistoryResponse,
)
def conversation_history(
    conversation_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> ConversationHistoryResponse:
    try:
        messages = list_messages(
            db, conversation_id, session.user_id, limit
        )
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=[_message_response(message) for message in messages],
        )
    except MessagingError as error:
        _raise_messaging_error(error)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=DirectMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: UUID,
    payload: MessageCreateRequest,
    db: Session = Depends(get_db),
    session: AuthenticatedSession = Depends(get_authenticated_session),
) -> DirectMessageResponse:
    try:
        message = send_message(
            db, conversation_id, session.user_id, payload.body
        )
        return _message_response(message)
    except MessagingError as error:
        _raise_messaging_error(error)
