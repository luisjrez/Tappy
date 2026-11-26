import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from tappy.payments.provider import PaymentEvidence, ProviderName

QR_PAYMENT_RECEIVED = "codi.qr.payment_received"
PHONE_PAYMENT_RECEIVED = "codi.pn.payment_received"
REQUEST_ID_FIELDS = {QR_PAYMENT_RECEIVED: "codiQrId", PHONE_PAYMENT_RECEIVED: "transactionId"}
CENTS_PER_PESO = Decimal(100)
TEXT_MAX_LENGTH = 64


def text(value: object) -> str | None:
    if isinstance(value, str) and 0 < len(value) <= TEXT_MAX_LENGTH:
        return value
    return None


def cents(value: object) -> int | None:
    if not isinstance(value, Decimal | int) or isinstance(value, bool):
        return None
    try:
        scaled = Decimal(value) * CENTS_PER_PESO
        if not scaled.is_finite() or scaled != scaled.to_integral_value() or scaled <= 0:
            return None
    except ArithmeticError:
        return None
    return int(scaled)


def paid_at(value: object) -> datetime | None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, UTC)
    except OverflowError, OSError, ValueError:
        return None


def invalid_bank_time(value: object) -> bool:
    return value is not None and paid_at(value) is None


def attempt_reference(metadata: object) -> uuid.UUID | None:
    if not isinstance(metadata, dict):
        return None
    try:
        return uuid.UUID(str(metadata.get("tappy_attempt_id")))
    except ValueError:
        return None


def evidence_from_pey(body: bytes, environment: str) -> PaymentEvidence | None:
    try:
        event = json.loads(body, parse_float=Decimal)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get("type") not in REQUEST_ID_FIELDS:
        return None
    return PaymentEvidence(
        provider=ProviderName.PEY,
        environment=environment,
        provider_request_id=text(event.get(REQUEST_ID_FIELDS[event["type"]])),
        attempt_id=attempt_reference(event.get("metadata")),
        provider_transaction_id=text(event.get("transactionId")),
        amount_cents=cents(event.get("amount")),
        receiver_account=text(event.get("bankAccountId")),
        occurred_at=paid_at(event.get("datePaid")),
        bank_time_invalid=invalid_bank_time(event.get("datePaid")),
    )
