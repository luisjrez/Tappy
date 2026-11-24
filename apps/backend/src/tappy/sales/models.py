import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tappy.merchants.models import BENEFICIARY_NAME_MAX_LENGTH
from tappy.platform.persistence import Base, enum_column

CONCEPT_MAX_LENGTH = 40
REFERENCE_LENGTH = 10
CURRENCY = "MXN"
REFERENCE_CONSTRAINT = "uq_sales_reference"


class SaleStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    REVIEW = "review"


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_sales_amount_cents_positive"),
        CheckConstraint(f"currency = '{CURRENCY}'", name="ck_sales_currency_mxn"),
        UniqueConstraint("reference", name=REFERENCE_CONSTRAINT),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merchants.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identities.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default=CURRENCY)
    concept: Mapped[str | None] = mapped_column(String(CONCEPT_MAX_LENGTH))
    reference: Mapped[str] = mapped_column(String(REFERENCE_LENGTH))
    status: Mapped[SaleStatus] = mapped_column(
        enum_column(SaleStatus, "sale_status"), default=SaleStatus.OPEN
    )
    receiving_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("receiving_accounts.id"))
    beneficiary_name: Mapped[str] = mapped_column(String(BENEFICIARY_NAME_MAX_LENGTH))
    account_last4: Mapped[str] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
