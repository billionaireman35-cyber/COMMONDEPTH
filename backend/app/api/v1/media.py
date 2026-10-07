from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authenticated_session,
    get_media_storage,
)
from app.core.database import get_db
from app.integrations.media_storage import MediaStorage
from app.schemas.media import (
    MediaUploadCompleteResponse,
    MediaUploadCreateRequest,
    MediaUploadCreateResponse,
)
from app.services.media import (
    MediaStorageError,
    MediaValidationError,
    complete_media_upload,
    create_media_upload,
)
from app.services.session_authentication import AuthenticatedSession


router = APIRouter(prefix="/media", tags=["media"])


@router.post(
    "/uploads",
    response_model=MediaUploadCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_upload(
    payload: MediaUploadCreateRequest,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    storage: MediaStorage = Depends(get_media_storage),
    db: Session = Depends(get_db),
) -> MediaUploadCreateResponse:
    try:
        result = create_media_upload(
            db,
            storage=storage,
            owner_id=authenticated.user_id,
            media_type=payload.media_type,
            mime_type=payload.mime_type,
            file_size=payload.file_size,
        )
    except MediaValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from None
    except MediaStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Media upload could not be created.",
        ) from None

    return MediaUploadCreateResponse(
        asset_id=result.asset.id,
        upload_id=result.upload.id,
        storage_provider=result.allocation.storage_provider,
        storage_key=result.allocation.storage_key,
        upload_url=result.allocation.upload_url,
        expires_at=result.allocation.expires_at,
    )


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=MediaUploadCompleteResponse,
)
def complete_upload(
    upload_id: UUID,
    authenticated: AuthenticatedSession = Depends(
        get_authenticated_session
    ),
    storage: MediaStorage = Depends(get_media_storage),
    db: Session = Depends(get_db),
) -> MediaUploadCompleteResponse:
    try:
        result = complete_media_upload(
            db,
            storage=storage,
            owner_id=authenticated.user_id,
            upload_id=upload_id,
        )
    except MediaValidationError as exc:
        message = str(exc)

        if "not found" in message.lower():
            http_status = status.HTTP_404_NOT_FOUND
        elif "does not belong" in message.lower():
            http_status = status.HTTP_403_FORBIDDEN
        else:
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY

        raise HTTPException(
            status_code=http_status,
            detail=message,
        ) from None
    except MediaStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Media upload could not be completed.",
        ) from None

    return MediaUploadCompleteResponse(
        asset_id=result.asset.id,
        upload_id=result.upload.id,
        upload_status=result.upload.status,
        asset_status=result.asset.status,
        completed_at=result.upload.completed_at,
    )
