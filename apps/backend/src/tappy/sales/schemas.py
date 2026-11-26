import uuid
from datetime import date, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, model_validator

from tappy.sales.exception_review import RequestOutcome
from tappy.sales.history import HistoryQuery
from tappy.sales.models import (
    NOTE_MAX_LENGTH,
    AttemptMethod,
    AttemptStatus,
    ExceptionReason,
    JobStatus,
    SaleStatus,
)
from tappy.sales.periods import PeriodKind
from tappy.sales.service import DateBasis, NextAction


class SaleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: uuid.UUID
    amount_cents: StrictInt
    concept: str | None = None


class AttemptCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: AttemptMethod
    phone_number: str | None = Field(default=None, max_length=32)


class AttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sale_id: str
    sale_reference: str
    method: AttemptMethod
    status: AttemptStatus
    simulated: bool
    provider_request_id: str | None
    qr_payload: str | None
    provider_folio: str | None
    payer_phone: str | None
    failure_code: str | None
    created_at: datetime
    expires_at: datetime | None
    next_action: NextAction
    verified_at: datetime | None
    withdrawn_at: datetime | None
    previous_attempt_id: str | None
    late_payment_possible: bool


class TransferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider_transaction_id: str
    amount_cents: int
    occurred_at: datetime | None
    dated_by: DateBasis
    received_at: datetime
    beneficiary_name: str
    masked_account: str


class ExceptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reason: ExceptionReason
    expected_amount_cents: int | None
    received_amount_cents: int | None
    created_at: datetime
    resolved_at: datetime | None


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    reference: str
    amount_cents: int
    currency: str
    concept: str | None
    status: SaleStatus
    beneficiary_name: str
    masked_account: str
    created_at: datetime
    attempts: list[AttemptResponse]
    confirmed_amount_cents: int
    covered: bool
    transfers: list[TransferResponse]
    exceptions: list[ExceptionResponse]


class HistoryParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: uuid.UUID | None = None
    status: SaleStatus | None = None
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None
    limit: int = Field(default=20, ge=1, le=50)
    cursor: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        if self.created_from and self.created_to and self.created_from >= self.created_to:
            raise ValueError("created_from must be before created_to")
        return self

    def to_query(self) -> HistoryQuery:
        return HistoryQuery(
            merchant_id=self.merchant_id,
            status=self.status,
            created_from=self.created_from,
            created_to=self.created_to,
            limit=self.limit,
            cursor=self.cursor,
        )


class SaleRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_id: str
    reference: str
    amount_cents: int
    currency: str
    concept: str | None
    status: SaleStatus
    covered: bool
    confirmed_amount_cents: int
    attempt_count: int
    beneficiary_name: str
    masked_account: str
    created_at: datetime


class HistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[SaleRowResponse]
    next_cursor: str | None


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sale_id: str
    sale_reference: str
    merchant_name: str
    beneficiary_name: str
    masked_account: str
    amount_cents: int
    currency: str
    concept: str | None
    provider_transaction_id: str
    paid_at: datetime | None
    dated_by: DateBasis
    received_at: datetime
    simulated: bool
    under_review: bool


class DailySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_id: str
    date: date
    timezone: str
    received_amount_cents: int
    currency: str
    transfer_count: int
    covered_sale_count: int
    review_sale_count: int
    open_exception_count: int


class PeriodParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: PeriodKind
    day: date | None = Field(default=None, alias="date")


class DayTotalsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    received_amount_cents: int
    transfer_count: int
    covered_sale_count: int


class PeriodSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    merchant_id: str
    period: PeriodKind
    start: date
    end: date
    timezone: str
    received_amount_cents: int
    currency: str
    transfer_count: int
    covered_sale_count: int
    review_sale_count: int
    open_exception_count: int
    reception_dated_transfer_count: int
    days: list[DayTotalsResponse]


class NoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=NOTE_MAX_LENGTH)


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    author: str
    text: str
    created_at: datetime


class ReviewJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: JobStatus
    run_at: datetime
    tries: int
    last_problem: str | None


class RequestedReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outcome: RequestOutcome
    job: ReviewJobResponse


class ExceptionDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reason: ExceptionReason
    sale_id: str | None
    sale_reference: str | None
    event_id: str | None
    provider_transaction_id: str | None
    expected_amount_cents: int | None
    received_amount_cents: int | None
    created_at: datetime
    resolved_at: datetime | None
    notes: list[NoteResponse]
    reconciliation: ReviewJobResponse | None
