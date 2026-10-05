from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import Device, PasswordCredential, Session, User, UserIdentity


class IdentityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_identity_by_provider_subject(
        self,
        provider: str,
        provider_subject: str,
    ) -> UserIdentity | None:
        statement = select(UserIdentity).where(
            UserIdentity.provider == provider,
            UserIdentity.provider_subject == provider_subject,
        )
        return self.db.scalar(statement)

    def get_user(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def add_user(self, user: User) -> User:
        self.db.add(user)
        return user

    def add_identity(self, identity: UserIdentity) -> UserIdentity:
        self.db.add(identity)
        return identity

    def add_password_credential(
        self,
        credential: PasswordCredential,
    ) -> PasswordCredential:
        self.db.add(credential)
        return credential

    def add_device(self, device: Device) -> Device:
        self.db.add(device)
        return device

    def add_session(self, session: Session) -> Session:
        self.db.add(session)
        return session
