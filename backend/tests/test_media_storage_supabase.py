from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.integrations.media_storage.supabase import SupabaseS3MediaStorage


def make_storage(client: Mock) -> SupabaseS3MediaStorage:
    storage = SupabaseS3MediaStorage(
        endpoint_url="https://example.storage.supabase.co/storage/v1/s3",
        region_name="eu-west-1",
        access_key="test-access-key",
        secret_key="test-secret-key",
        bucket="common",
    )
    storage.client = client
    return storage


def test_allocate_upload_generates_presigned_put_url():
    client = Mock()
    client.generate_presigned_url.return_value = "https://signed-upload.example"

    storage = make_storage(client)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    result = storage.allocate_upload(
        storage_key="media/user/image/test.jpg",
        mime_type="image/jpeg",
        file_size=1024,
        expires_at=expires_at,
    )

    assert result.storage_provider == "supabase"
    assert result.storage_key == "media/user/image/test.jpg"
    assert result.upload_url == "https://signed-upload.example"
    assert result.expires_at == expires_at

    client.generate_presigned_url.assert_called_once()
    args, kwargs = client.generate_presigned_url.call_args

    assert args == ("put_object",)
    assert kwargs["Params"] == {
        "Bucket": "common",
        "Key": "media/user/image/test.jpg",
        "ContentType": "image/jpeg",
    }
    assert 1 <= kwargs["ExpiresIn"] <= 1800


def test_inspect_object_maps_s3_metadata():
    client = Mock()
    client.head_object.return_value = {
        "ContentLength": 2048,
        "ContentType": "image/webp",
    }

    storage = make_storage(client)

    result = storage.inspect_object(
        storage_key="media/user/image/test.webp",
    )

    assert result.storage_provider == "supabase"
    assert result.storage_key == "media/user/image/test.webp"
    assert result.file_size == 2048
    assert result.mime_type == "image/webp"

    client.head_object.assert_called_once_with(
        Bucket="common",
        Key="media/user/image/test.webp",
    )


def test_delete_object_deletes_expected_key():
    client = Mock()
    storage = make_storage(client)

    storage.delete_object(
        storage_key="media/user/image/test.webp",
    )

    client.delete_object.assert_called_once_with(
        Bucket="common",
        Key="media/user/image/test.webp",
    )


def test_get_read_url_generates_presigned_get_url():
    client = Mock()
    client.generate_presigned_url.return_value = "https://signed-read.example"

    storage = make_storage(client)

    result = storage.get_read_url(
        storage_key="media/user/image/test.webp",
    )

    assert result == "https://signed-read.example"

    client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={
            "Bucket": "common",
            "Key": "media/user/image/test.webp",
        },
        ExpiresIn=900,
    )
