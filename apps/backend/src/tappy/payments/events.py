import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import DateTime, LargeBinary, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from tappy.payments.provider import ProviderName
from tappy.payments.webhooks import EVENT_ID_MAX_LENGTH
from tappy.platform.persistence import Base, enum_column

EVENT_CONSTRAINT = "uq_webhook_events_provider_event"
EVENT_TYPE_MAX_LENGTH = 64


class EventStatus(StrEnum):
    RECEIVED = "received"


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "provider_event_id", name=EVENT_CONSTRAINT),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[ProviderName] = mapped_column(enum_column(ProviderName, "webhook_provider"))
    provider_event_id: Mapped[str] = mapped_column(String(EVENT_ID_MAX_LENGTH))
    event_type: Mapped[str] = mapped_column(String(EVENT_TYPE_MAX_LENGTH))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    payload_digest: Mapped[str] = mapped_column(String(64))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[EventStatus] = mapped_column(enum_column(EventStatus, "webhook_event_status"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InvalidEventError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid webhook event")


class EventEnvelope(BaseModel):
    type: str = Field(min_length=1, max_length=EVENT_TYPE_MAX_LENGTH)
    data: dict[str, object]


def envelope_of(body: bytes) -> EventEnvelope:
    try:
        return EventEnvelope.model_validate_json(body)
    except ValidationError:
        raise InvalidEventError from None


@dataclass(frozen=True)
class ReceivedEvent:
    provider: ProviderName
    message_id: str
    event_type: str
    body: bytes
    signed_at: datetime


def store_event(db: Session, event: ReceivedEvent, now: datetime) -> None:
    db.execute(
        insert(WebhookEvent)
        .values(
            id=uuid.uuid4(),
            provider=event.provider,
            provider_event_id=event.message_id,
            event_type=event.event_type,
            payload=event.body,
            payload_digest=hashlib.sha256(event.body).hexdigest(),
            signed_at=event.signed_at,
            status=EventStatus.RECEIVED,
            received_at=now,
        )
        .on_conflict_do_nothing(constraint=EVENT_CONSTRAINT)
    )
