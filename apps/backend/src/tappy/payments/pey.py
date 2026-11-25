import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from tappy.payments.pey_events import cents, paid_at
from tappy.payments.provider import (
    IssuedQr,
    PaymentsQueryError,
    ProviderName,
    ProviderRejectedError,
    ProviderUnavailableError,
    QrOrder,
    QrPayment,
    QueryProblem,
    UncertainReason,
)
from tappy.platform.config import MAX_QUERY_PAGES

logger = logging.getLogger(__name__)
CENTS_PER_PESO = Decimal(100)
REJECTED_STATUSES = frozenset({400, 429})
MAX_RETRY_AFTER_SECONDS = 24 * 3600
PAID = "PAID"
NETWORK_PROBLEMS = {
    UncertainReason.TIMEOUT: QueryProblem.TIMEOUT,
    UncertainReason.CONNECTION: QueryProblem.CONNECTION,
}
QUERY_PROBLEMS: dict[int, QueryProblem] = {
    httpx2.codes.NOT_FOUND: QueryProblem.NOT_FOUND,
    httpx2.codes.TOO_MANY_REQUESTS: QueryProblem.RATE_LIMITED,
    httpx2.codes.BAD_REQUEST: QueryProblem.REJECTED,
}


@dataclass(frozen=True)
class PeySettings:
    base_url: str
    api_key: SecretStr
    timeout_seconds: float
    qr_window: timedelta


class CreatedQr(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str = Field(min_length=1, max_length=64)
    qr_string: str = Field(alias="qrString", min_length=1)


class ErrorDetail(BaseModel):
    type: str = Field(pattern=r"^[A-Z_]{1,32}$")


class ErrorBody(BaseModel):
    error: ErrorDetail


class QueryItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    status: str
    amount: object = None
    date_paid: object = Field(default=None, alias="datePaid")


class QueryPage(BaseModel):
    items: list[QueryItem]
    next_token: str | None = Field(default=None, alias="nextToken", min_length=1)


def pesos(amount_cents: int) -> float:
    exact = Decimal(amount_cents) / CENTS_PER_PESO
    sent = float(exact)
    if Decimal(repr(sent)) != exact:
        raise ValueError("Amount cannot be represented exactly in pesos")
    return sent


def qr_request(order: QrOrder, qr_window: timedelta) -> dict[str, object]:
    body: dict[str, object] = {
        "amount": pesos(order.amount_cents),
        "bankAccountId": order.receiver_account,
        "expiration": int(qr_window.total_seconds()),
        "metadata": {"tappy_attempt_id": str(order.attempt_id), "tappy_reference": order.reference},
    }
    if order.concept is not None:
        body["concept"] = order.concept
    return body


def rejection_code(response: httpx2.Response) -> str:
    try:
        return ErrorBody.model_validate_json(response.content).error.type
    except ValidationError:
        raise ProviderUnavailableError(UncertainReason.INVALID_RESPONSE) from None


def issued_qr(response: httpx2.Response, valid_for: timedelta) -> IssuedQr:
    try:
        created = CreatedQr.model_validate_json(response.content)
    except ValidationError:
        raise ProviderUnavailableError(UncertainReason.INVALID_RESPONSE) from None
    return IssuedQr(created.id, created.qr_string, valid_for)


def retry_after(response: httpx2.Response) -> timedelta | None:
    value = response.headers.get("Retry-After", "")
    if not value.isascii() or not value.isdigit():
        return None
    if len(value) > len(str(MAX_RETRY_AFTER_SECONDS)):
        return timedelta(seconds=MAX_RETRY_AFTER_SECONDS)
    return timedelta(seconds=min(int(value), MAX_RETRY_AFTER_SECONDS))


def query_page(response: httpx2.Response) -> QueryPage:
    if response.status_code != httpx2.codes.OK:
        problem = QUERY_PROBLEMS.get(response.status_code, QueryProblem.SERVER_ERROR)
        raise PaymentsQueryError(problem, retry_after(response))
    try:
        return QueryPage.model_validate(json.loads(response.content, parse_float=Decimal))
    except ValueError:
        raise PaymentsQueryError(QueryProblem.INVALID_RESPONSE) from None


def paid_payments(page: QueryPage) -> list[QrPayment]:
    return [
        QrPayment(item.id, cents(item.amount), paid_at(item.date_paid))
        for item in page.items
        if item.status == PAID
    ]


class PeyQrProvider:
    name = ProviderName.PEY
    simulated = False

    def __init__(self, settings: PeySettings, transport: httpx2.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    @contextmanager
    def client(self) -> Iterator[httpx2.Client]:
        with httpx2.Client(
            base_url=self.settings.base_url,
            timeout=self.settings.timeout_seconds,
            transport=self.transport,
            headers={"Authorization": f"Bearer {self.settings.api_key.get_secret_value()}"},
        ) as client:
            try:
                yield client
            except httpx2.TimeoutException:
                raise ProviderUnavailableError(UncertainReason.TIMEOUT) from None
            except httpx2.TransportError:
                raise ProviderUnavailableError(UncertainReason.CONNECTION) from None

    def post(self, order: QrOrder) -> httpx2.Response:
        with self.client() as client:
            return client.post("/codi/qr", json=qr_request(order, self.settings.qr_window))

    def qr_payments(self, provider_request_id: str) -> list[QrPayment]:
        path = f"/transaction/codi/qr/{quote(provider_request_id, safe='')}"
        payments: list[QrPayment] = []
        params: dict[str, str] = {}
        try:
            with self.client() as client:
                for _ in range(MAX_QUERY_PAGES):
                    page = query_page(client.get(path, params=params))
                    payments.extend(paid_payments(page))
                    if page.next_token is None:
                        return payments
                    params = {"nextToken": page.next_token}
        except ProviderUnavailableError as error:
            raise PaymentsQueryError(NETWORK_PROBLEMS[error.reason]) from None
        raise PaymentsQueryError(QueryProblem.TOO_MANY_PAGES)

    def create_qr(self, order: QrOrder) -> IssuedQr:
        response = self.post(order)
        logger.info(
            "pey QR creation for attempt %s answered %s", order.attempt_id, response.status_code
        )
        if response.status_code == httpx2.codes.CREATED:
            return issued_qr(response, self.settings.qr_window)
        if response.status_code in REJECTED_STATUSES:
            raise ProviderRejectedError(rejection_code(response))
        raise ProviderUnavailableError(UncertainReason.SERVER_ERROR)
