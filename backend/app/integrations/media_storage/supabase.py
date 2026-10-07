from datetime import datetime, timezone

import boto3
from botocore.client import Config

from app.core.config import get_settings
from app.integrations.media_storage.protocol import (
    StorageObject,
    UploadAllocation,
)


_READ_URL_EXPIRY_SECONDS = 900


class SupabaseS3MediaStorage:
    """S3-compatible MediaStorage adapter for Supabase Storage."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        region_name: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ) -> None:
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

    def allocate_upload(
        self,
        *,
        storage_key: str,
        mime_type: str,
        file_size: int,
        expires_at: object,
    ) -> UploadAllocation:
        if not isinstance(expires_at, datetime):
            raise ValueError("expires_at must be a datetime.")

        now = datetime.now(timezone.utc)
        expiry = expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        expires_in = max(1, int((expiry - now).total_seconds()))

        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": storage_key,
                "ContentType": mime_type,
            },
            ExpiresIn=expires_in,
        )

        return UploadAllocation(
            storage_provider="supabase",
            storage_key=storage_key,
            upload_url=upload_url,
            expires_at=expires_at,
        )

    def inspect_object(
        self,
        *,
        storage_key: str,
    ) -> StorageObject:
        response = self.client.head_object(
            Bucket=self.bucket,
            Key=storage_key,
        )

        return StorageObject(
            storage_provider="supabase",
            storage_key=storage_key,
            file_size=int(response["ContentLength"]),
            mime_type=response.get("ContentType", "application/octet-stream"),
        )

    def delete_object(
        self,
        *,
        storage_key: str,
    ) -> None:
        self.client.delete_object(
            Bucket=self.bucket,
            Key=storage_key,
        )

    def get_read_url(
        self,
        *,
        storage_key: str,
    ) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": storage_key,
            },
            ExpiresIn=_READ_URL_EXPIRY_SECONDS,
        )


def get_supabase_s3_storage() -> SupabaseS3MediaStorage:
    settings = get_settings()

    return SupabaseS3MediaStorage(
        endpoint_url=settings.supabase_s3_endpoint,
        region_name=settings.supabase_s3_region,
        access_key=settings.supabase_s3_access_key,
        secret_key=settings.supabase_s3_secret_key,
        bucket=settings.supabase_s3_bucket,
    )
