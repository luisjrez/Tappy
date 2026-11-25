import base64
import binascii
import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import SecretStr

from tappy.platform.config import standard_webhook_key

SIGNATURE_VERSION = "v1"
EVENT_ID_MAX_LENGTH = 255
TIMESTAMP = re.compile(r"\d{1,12}")


class InvalidSignatureError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid webhook signature")


@dataclass(frozen=True)
class SignedDelivery:
    message_id: str
    timestamp: str
    signatures: str
    body: bytes


def expected_signature(secret: SecretStr, delivery: SignedDelivery) -> bytes:
    signed = f"{delivery.message_id}.{delivery.timestamp}.".encode() + delivery.body
    key = standard_webhook_key(secret.get_secret_value())
    return hmac.new(key, signed, hashlib.sha256).digest()


def presented_signatures(header: str) -> list[bytes]:
    decoded = []
    for entry in header.split():
        version, _, value = entry.partition(",")
        if version != SIGNATURE_VERSION:
            continue
        try:
            decoded.append(base64.b64decode(value, validate=True))
        except binascii.Error:
            continue
    return decoded


def verify(secret: SecretStr, delivery: SignedDelivery, now: datetime, tolerance: int) -> datetime:
    if not 0 < len(delivery.message_id) <= EVENT_ID_MAX_LENGTH:
        raise InvalidSignatureError
    if not TIMESTAMP.fullmatch(delivery.timestamp):
        raise InvalidSignatureError
    signed_at = int(delivery.timestamp)
    if abs(now.timestamp() - signed_at) > tolerance:
        raise InvalidSignatureError
    expected = expected_signature(secret, delivery)
    presented = presented_signatures(delivery.signatures)
    if not any(hmac.compare_digest(expected, given) for given in presented):
        raise InvalidSignatureError
    return datetime.fromtimestamp(signed_at, UTC)
