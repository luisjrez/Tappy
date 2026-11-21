import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tappy.platform.persistence import Base

MERCHANT_NAME_MAX_LENGTH = 120


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(MERCHANT_NAME_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("merchant_id", "identity_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), index=True)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identities.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
