import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from tappy.platform.persistence import Base, enum_column


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class OutboundEmail(Base):
    __tablename__ = "outbound_emails"
    __table_args__ = (Index("ix_outbound_emails_due", "status", "next_attempt_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(200))
    sealed_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[DeliveryStatus] = mapped_column(enum_column(DeliveryStatus, "delivery_status"))
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
