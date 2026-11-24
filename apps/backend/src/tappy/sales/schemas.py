import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictInt

from tappy.sales.models import AttemptMethod, AttemptStatus, SaleStatus


class SaleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    merchant_id: uuid.UUID
    amount_cents: StrictInt
    concept: str | None = None


class AttemptCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: AttemptMethod


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
    failure_code: str | None
    created_at: datetime


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
