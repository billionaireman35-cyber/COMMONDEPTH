from datetime import datetime, timezone
from uuid import uuid4

from app.core.database import SessionLocal
from app.models.identity import Device, PasswordCredential, Session, User, UserIdentity
from app.repositories.identity import IdentityRepository


def test_identity_repository_persistence_and_lookup() -> None:
    db = SessionLocal()

    try:
        repository = IdentityRepository(db)

        user = User()
        repository.add_user(user)
        db.flush()

        identity = UserIdentity(
            user_id=user.id,
            provider="email",
            provider_subject=f"repository-test-{uuid4()}@example.invalid",
        )
        repository.add_identity(identity)
        db.flush()

        credential = PasswordCredential(
            user_identity_id=identity.id,
            password_hash="repository-test-hash",
            password_changed_at=datetime.now(timezone.utc),
        )
        repository.add_password_credential(credential)

        device = Device(
            user_id=user.id,
            platform="test",
        )
        repository.add_device(device)
        db.flush()

        session = Session(
            user_id=user.id,
            device_id=device.id,
            token_hash=f"repository-test-token-{uuid4()}",
            expires_at=datetime.now(timezone.utc),
        )
        repository.add_session(session)
        db.flush()

        assert repository.get_user(user.id) is user

        found = repository.get_identity_by_provider_subject(
            "email",
            identity.provider_subject,
        )
        assert found is identity
        assert found.user_id == user.id
        assert credential.user_identity_id == identity.id
        assert device.user_id == user.id
        assert session.user_id == user.id
        assert session.device_id == device.id
    finally:
        db.rollback()
        db.close()
