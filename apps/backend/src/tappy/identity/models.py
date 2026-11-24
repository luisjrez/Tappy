import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from tappy.platform.persistence import Base, enum_column


class Role(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"


class IdentityStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Identity(Base):
    __tablename__ = "identities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role, "identity_role"))
    status: Mapped[IdentityStatus] = mapped_column(enum_column(IdentityStatus, "identity_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("uq_identities_email_lower", func.lower(Identity.email), unique=True)


class AccessSession(Base):
    __tablename__ = "access_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    family_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
