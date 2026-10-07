from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UploadAllocation:
    storage_provider: str
    storage_key: str
    upload_url: str
    expires_at: object


@dataclass(frozen=True)
class StorageObject:
    storage_provider: str
    storage_key: str
    file_size: int
    mime_type: str


class MediaStorage(Protocol):
    def allocate_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        file_size: int,
        expires_at: object,
    ) -> UploadAllocation:
        ...

    def inspect_object(
        self,
        *,
        storage_key: str,
    ) -> StorageObject:
        ...

    def delete_object(
        self,
        *,
        storage_key: str,
    ) -> None:
        ...

    def get_read_url(
        self,
        *,
        storage_key: str,
    ) -> str:
        ...
