import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, func
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
    __table_args__ = (Index("uq_identities_email_lower", func.lower("email"), unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role, "identity_role"))
    status: Mapped[IdentityStatus] = mapped_column(enum_column(IdentityStatus, "identity_status"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
