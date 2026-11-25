import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from tappy.payments.events import EventStatus, WebhookEvent
from tappy.payments.pey_events import evidence_from_pey
from tappy.payments.provider import ProviderName
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.sales.evidence import apply_evidence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingSummary:
    applied: int
    unmatched: int
    failed: int


def held_received_event(db: Session, event_id: uuid.UUID) -> WebhookEvent | None:
    return db.scalar(
        select(WebhookEvent)
        .where(WebhookEvent.id == event_id, WebhookEvent.status == EventStatus.RECEIVED)
        .with_for_update(skip_locked=True)
    )


def process_event(database: Database, event_id: uuid.UUID, clock: Clock) -> EventStatus | None:
    with database.transaction() as db:
        event = held_received_event(db, event_id)
        if event is None:
            return None
        evidence = evidence_from_pey(event.payload)
        applied = evidence is not None and apply_evidence(db, evidence, event.id, clock.now())
        event.status = EventStatus.APPLIED if applied else EventStatus.UNMATCHED
        return event.status


def stored_event_id(database: Database, provider: ProviderName, message_id: str) -> uuid.UUID:
    with database.transaction() as db:
        return db.scalars(
            select(WebhookEvent.id).where(
                WebhookEvent.provider == provider, WebhookEvent.provider_event_id == message_id
            )
        ).one()


def process_safely(database: Database, event_id: uuid.UUID, clock: Clock) -> EventStatus | None:
    try:
        return process_event(database, event_id, clock)
    except SQLAlchemyError as error:
        logger.error(
            "Webhook event %s could not be applied (%s); it stays received",
            event_id,
            type(error).__name__,
        )
        return None


def process_stored(
    database: Database, provider: ProviderName, message_id: str, clock: Clock
) -> EventStatus | None:
    try:
        event_id = stored_event_id(database, provider, message_id)
    except SQLAlchemyError as error:
        logger.error("Stored webhook event could not be read (%s)", type(error).__name__)
        return None
    return process_safely(database, event_id, clock)


def process_received_events(database: Database, clock: Clock) -> ProcessingSummary:
    with database.transaction() as db:
        pending = db.scalars(
            select(WebhookEvent.id)
            .where(WebhookEvent.status == EventStatus.RECEIVED)
            .order_by(WebhookEvent.received_at, WebhookEvent.id)
        ).all()
    outcomes = [process_safely(database, event_id, clock) for event_id in pending]
    return ProcessingSummary(
        applied=outcomes.count(EventStatus.APPLIED),
        unmatched=outcomes.count(EventStatus.UNMATCHED),
        failed=outcomes.count(None),
    )
