import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from tappy.platform.persistence import Base, enum_column

KEY_PATTERN = r"^[A-Za-z0-9_-]{8,128}$"
KEY_MAX_LENGTH = 128
KEY_CONSTRAINT = "uq_idempotency_requests_key"


class IdempotentOperation(StrEnum):
    CREATE_SALE = "create_sale"


class IdempotencyRequest(Base):
    __tablename__ = "idempotency_requests"
    __table_args__ = (UniqueConstraint("identity_id", "operation", "key", name=KEY_CONSTRAINT),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    identity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identities.id"))
    operation: Mapped[IdempotentOperation] = mapped_column(
        enum_column(IdempotentOperation, "idempotent_operation")
    )
    key: Mapped[str] = mapped_column(String(KEY_MAX_LENGTH))
    request_digest: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyConflictError(Exception):
    def __init__(self) -> None:
        super().__init__("Idempotency key already used with different content")


@dataclass(frozen=True)
class IdempotencyClaim:
    identity_id: uuid.UUID
    operation: IdempotentOperation
    key: str
    request_digest: str


def digest_of(content: Mapping[str, object]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def claim_or_replay(
    db: Session, claim: IdempotencyClaim, resource_id: uuid.UUID, now: datetime
) -> uuid.UUID | None:
    reserved = db.scalar(
        insert(IdempotencyRequest)
        .values(
            id=uuid.uuid4(),
            identity_id=claim.identity_id,
            operation=claim.operation,
            key=claim.key,
            request_digest=claim.request_digest,
            resource_id=resource_id,
            created_at=now,
        )
        .on_conflict_do_nothing(constraint=KEY_CONSTRAINT)
        .returning(IdempotencyRequest.id)
    )
    if reserved is not None:
        return None
    stored = db.scalars(
        select(IdempotencyRequest).where(
            IdempotencyRequest.identity_id == claim.identity_id,
            IdempotencyRequest.operation == claim.operation,
            IdempotencyRequest.key == claim.key,
        )
    ).one()
    if stored.request_digest != claim.request_digest:
        raise IdempotencyConflictError
    return stored.resource_id
