import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

ENVIRONMENT_MAX_LENGTH = 32


class ProviderName(StrEnum):
    SIMULATED = "simulated"
    PEY = "pey"


class UncertainReason(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVER_ERROR = "server_error"
    INVALID_RESPONSE = "invalid_response"
    DUPLICATE_PROVIDER_ID = "duplicate_provider_id"


class ProviderUnavailableError(Exception):
    def __init__(self, reason: UncertainReason) -> None:
        super().__init__(f"QR provider unavailable: {reason}")
        self.reason = reason


class QueryProblem(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVER_ERROR = "server_error"
    INVALID_RESPONSE = "invalid_response"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    REJECTED = "rejected"
    TOO_MANY_PAGES = "too_many_pages"


class PaymentsQueryError(Exception):
    def __init__(self, problem: QueryProblem, retry_after: timedelta | None = None) -> None:
        super().__init__(f"QR payments query failed: {problem}")
        self.problem = problem
        self.retry_after = retry_after


class ProviderRejectedError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(f"QR provider rejected the request: {code}")
        self.code = code


@dataclass(frozen=True)
class QrOrder:
    attempt_id: uuid.UUID
    reference: str
    amount_cents: int
    concept: str | None
    receiver_account: str


@dataclass(frozen=True)
class IssuedQr:
    provider_request_id: str
    payload: str
    valid_for: timedelta | None = None


@dataclass(frozen=True)
class QrPayment:
    transaction_id: str
    amount_cents: int | None
    occurred_at: datetime | None
    bank_time_invalid: bool = False


class QrProvider(Protocol):
    @property
    def name(self) -> ProviderName: ...

    @property
    def simulated(self) -> bool: ...

    def create_qr(self, order: QrOrder) -> IssuedQr: ...

    def qr_payments(self, provider_request_id: str) -> list[QrPayment]: ...


@dataclass(frozen=True)
class PaymentEvidence:
    provider: ProviderName
    environment: str
    provider_request_id: str | None
    attempt_id: uuid.UUID | None
    provider_transaction_id: str | None
    amount_cents: int | None
    receiver_account: str | None
    occurred_at: datetime | None
    bank_time_invalid: bool = False
