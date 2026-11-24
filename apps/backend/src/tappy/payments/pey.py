import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx2
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from tappy.payments.provider import (
    IssuedQr,
    ProviderName,
    ProviderRejectedError,
    ProviderUnavailableError,
    QrOrder,
)

logger = logging.getLogger(__name__)
CENTS_PER_PESO = Decimal(100)
REJECTED_STATUSES = frozenset({400, 429})


@dataclass(frozen=True)
class PeySettings:
    base_url: str
    api_key: SecretStr
    timeout_seconds: float


class CreatedQr(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str = Field(min_length=1, max_length=64)
    qr_string: str = Field(alias="qrString", min_length=1)


class ErrorDetail(BaseModel):
    type: str = Field(pattern=r"^[A-Z_]{1,32}$")


class ErrorBody(BaseModel):
    error: ErrorDetail


def pesos(amount_cents: int) -> float:
    exact = Decimal(amount_cents) / CENTS_PER_PESO
    sent = float(exact)
    if Decimal(repr(sent)) != exact:
        raise ValueError("Amount cannot be represented exactly in pesos")
    return sent


def qr_request(order: QrOrder) -> dict[str, object]:
    body: dict[str, object] = {
        "amount": pesos(order.amount_cents),
        "bankAccountId": order.receiver_account,
        "metadata": {"tappy_attempt_id": str(order.attempt_id), "tappy_reference": order.reference},
    }
    if order.concept is not None:
        body["concept"] = order.concept
    return body


def rejection_code(response: httpx2.Response) -> str:
    try:
        return ErrorBody.model_validate_json(response.content).error.type
    except ValidationError:
        raise ProviderUnavailableError("invalid_response") from None


def issued_qr(response: httpx2.Response) -> IssuedQr:
    try:
        created = CreatedQr.model_validate_json(response.content)
    except ValidationError:
        raise ProviderUnavailableError("invalid_response") from None
    return IssuedQr(created.id, created.qr_string)


class PeyQrProvider:
    name = ProviderName.PEY
    simulated = False

    def __init__(self, settings: PeySettings, transport: httpx2.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def post(self, order: QrOrder) -> httpx2.Response:
        headers = {"Authorization": f"Bearer {self.settings.api_key.get_secret_value()}"}
        with httpx2.Client(
            base_url=self.settings.base_url,
            timeout=self.settings.timeout_seconds,
            transport=self.transport,
        ) as client:
            try:
                return client.post("/codi/qr", json=qr_request(order), headers=headers)
            except httpx2.TimeoutException:
                raise ProviderUnavailableError("timeout") from None
            except httpx2.TransportError:
                raise ProviderUnavailableError("connection") from None

    def create_qr(self, order: QrOrder) -> IssuedQr:
        response = self.post(order)
        logger.info(
            "pey QR creation for attempt %s answered %s", order.attempt_id, response.status_code
        )
        if response.status_code == httpx2.codes.CREATED:
            return issued_qr(response)
        if response.status_code in REJECTED_STATUSES:
            raise ProviderRejectedError(rejection_code(response))
        raise ProviderUnavailableError("server_error")
