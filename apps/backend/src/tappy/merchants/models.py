import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tappy.platform.persistence import Base

MERCHANT_NAME_MAX_LENGTH = 120
BENEFICIARY_NAME_MAX_LENGTH = 120
PROVIDER_ACCOUNT_ID_MAX_LENGTH = 64
PROVIDER_ACCOUNT_CONSTRAINT = "uq_receiving_accounts_provider_account_id"


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


class ReceivingAccount(Base):
    __tablename__ = "receiving_accounts"
    __table_args__ = (UniqueConstraint("provider_account_id", name=PROVIDER_ACCOUNT_CONSTRAINT),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), unique=True)
    provider_account_id: Mapped[str] = mapped_column(String(PROVIDER_ACCOUNT_ID_MAX_LENGTH))
    beneficiary_name: Mapped[str] = mapped_column(String(BENEFICIARY_NAME_MAX_LENGTH))
    account_last4: Mapped[str] = mapped_column(String(4))
    enabled: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
