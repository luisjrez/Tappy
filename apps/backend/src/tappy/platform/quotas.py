import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Integer, String, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from tappy.platform.persistence import Base, enum_column

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


class QuotaOperation(StrEnum):
    SALE_CREATION = "sale_creation"
    ATTEMPT_CREATION = "attempt_creation"
    SALE_READ = "sale_read"


class OperationQuota(Base):
    __tablename__ = "operation_quotas"
    __table_args__ = (CheckConstraint("used > 0", name="operation_quota_used"),)

    scope: Mapped[str] = mapped_column(String(64), primary_key=True)
    operation: Mapped[QuotaOperation] = mapped_column(
        enum_column(QuotaOperation, "quota_operation"), primary_key=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    used: Mapped[int] = mapped_column(Integer)


@dataclass(frozen=True)
class QuotaPolicy:
    limit: int
    window: timedelta

    def window_start(self, now: datetime) -> datetime:
        seconds = self.window.total_seconds()
        return EPOCH + timedelta(seconds=(now - EPOCH).total_seconds() // seconds * seconds)

    def seconds_left(self, now: datetime) -> int:
        remaining = self.window_start(now) + self.window - now
        return max(1, math.ceil(remaining.total_seconds()))


def merchant_scope(merchant_id: uuid.UUID) -> str:
    return f"merchant:{merchant_id}"


def identity_scope(identity_id: uuid.UUID) -> str:
    return f"identity:{identity_id}"


class QuotaExceededError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"Quota exceeded; try again in {retry_after} seconds")
        self.retry_after = retry_after


def reserve_quota(
    db: Session, operation: QuotaOperation, scope: str, policy: QuotaPolicy, now: datetime
) -> None:
    start = policy.window_start(now)
    db.execute(
        delete(OperationQuota).where(
            OperationQuota.scope == scope,
            OperationQuota.operation == operation,
            OperationQuota.window_start < start,
        )
    )
    statement = insert(OperationQuota).values(
        scope=scope, operation=operation, window_start=start, used=1
    )
    used = db.scalar(
        statement.on_conflict_do_update(
            index_elements=[
                OperationQuota.scope,
                OperationQuota.operation,
                OperationQuota.window_start,
            ],
            set_={"used": OperationQuota.used + 1},
            where=OperationQuota.used < policy.limit,
        ).returning(OperationQuota.used)
    )
    if used is None:
        raise QuotaExceededError(policy.seconds_left(now))
