import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from tappy.payments.provider import ENVIRONMENT_MAX_LENGTH, ProviderName
from tappy.payments.webhooks import EVENT_ID_MAX_LENGTH
from tappy.platform.persistence import Base, enum_column

EVENT_CONSTRAINT = "uq_webhook_events_provider_event"
CONFLICT_CONSTRAINT = "uq_webhook_event_conflicts_variant"
EVENT_TYPE_MAX_LENGTH = 64


class EventStatus(StrEnum):
    RECEIVED = "received"
    APPLIED = "applied"
    UNMATCHED = "unmatched"
    DUPLICATE = "duplicate"
    REVIEW = "review"


class StoreOutcome(StrEnum):
    NEW = "new"
    REPEATED = "repeated"
    CONFLICT = "conflict"


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "environment", "provider_event_id", name=EVENT_CONSTRAINT),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    provider: Mapped[ProviderName] = mapped_column(enum_column(ProviderName, "webhook_provider"))
    environment: Mapped[str] = mapped_column(String(ENVIRONMENT_MAX_LENGTH))
    provider_event_id: Mapped[str] = mapped_column(String(EVENT_ID_MAX_LENGTH))
    event_type: Mapped[str] = mapped_column(String(EVENT_TYPE_MAX_LENGTH))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    payload_digest: Mapped[str] = mapped_column(String(64))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[EventStatus] = mapped_column(enum_column(EventStatus, "webhook_event_status"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebhookEventConflict(Base):
    __tablename__ = "webhook_event_conflicts"
    __table_args__ = (UniqueConstraint("event_id", "payload_digest", name=CONFLICT_CONSTRAINT),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("webhook_events.id"))
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    payload_digest: Mapped[str] = mapped_column(String(64))
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InvalidEventError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid webhook event")


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1, max_length=EVENT_TYPE_MAX_LENGTH)


def envelope_of(body: bytes) -> EventEnvelope:
    try:
        return EventEnvelope.model_validate_json(body)
    except ValidationError:
        raise InvalidEventError from None


@dataclass(frozen=True)
class ReceivedEvent:
    provider: ProviderName
    environment: str
    message_id: str
    event_type: str
    body: bytes
    signed_at: datetime


def stored_event(db: Session, event: ReceivedEvent) -> WebhookEvent:
    return db.scalars(
        select(WebhookEvent).where(
            WebhookEvent.provider == event.provider,
            WebhookEvent.environment == event.environment,
            WebhookEvent.provider_event_id == event.message_id,
        )
    ).one()


def store_event(db: Session, event: ReceivedEvent, now: datetime) -> StoreOutcome:
    digest = hashlib.sha256(event.body).hexdigest()
    inserted = db.scalar(
        insert(WebhookEvent)
        .values(
            id=uuid.uuid4(),
            provider=event.provider,
            environment=event.environment,
            provider_event_id=event.message_id,
            event_type=event.event_type,
            payload=event.body,
            payload_digest=digest,
            signed_at=event.signed_at,
            status=EventStatus.RECEIVED,
            received_at=now,
        )
        .on_conflict_do_nothing(constraint=EVENT_CONSTRAINT)
        .returning(WebhookEvent.id)
    )
    if inserted is not None:
        return StoreOutcome.NEW
    original = stored_event(db, event)
    if original.payload_digest == digest:
        return StoreOutcome.REPEATED
    db.execute(
        insert(WebhookEventConflict)
        .values(
            id=uuid.uuid4(),
            event_id=original.id,
            payload=event.body,
            payload_digest=digest,
            signed_at=event.signed_at,
            received_at=now,
        )
        .on_conflict_do_nothing(constraint=CONFLICT_CONSTRAINT)
    )
    return StoreOutcome.CONFLICT


def event_conflicts(db: Session) -> list[tuple[WebhookEvent, WebhookEventConflict]]:
    rows = db.execute(
        select(WebhookEvent, WebhookEventConflict)
        .join(WebhookEventConflict, WebhookEventConflict.event_id == WebhookEvent.id)
        .order_by(WebhookEventConflict.received_at, WebhookEventConflict.id)
    ).tuples()
    return list(rows)
