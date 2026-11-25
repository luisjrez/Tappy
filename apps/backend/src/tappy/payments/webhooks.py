import base64
import binascii
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime

from pydantic import SecretStr

SIGNATURE_VERSION = "v1"


class InvalidSignatureError(Exception):
    def __init__(self) -> None:
        super().__init__("Invalid webhook signature")


@dataclass(frozen=True)
class SignedDelivery:
    message_id: str
    timestamp: str
    signatures: str
    body: bytes


def signing_key(secret: SecretStr) -> bytes:
    return base64.b64decode(secret.get_secret_value().removeprefix("whsec_"))


def expected_signature(secret: SecretStr, delivery: SignedDelivery) -> bytes:
    signed = f"{delivery.message_id}.{delivery.timestamp}.".encode() + delivery.body
    return hmac.new(signing_key(secret), signed, hashlib.sha256).digest()


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


def verify(secret: SecretStr, delivery: SignedDelivery, now: datetime, tolerance: int) -> None:
    if not delivery.message_id or not delivery.timestamp.isdigit():
        raise InvalidSignatureError
    if abs(now.timestamp() - int(delivery.timestamp)) > tolerance:
        raise InvalidSignatureError
    expected = expected_signature(secret, delivery)
    if not any(
        hmac.compare_digest(expected, given) for given in presented_signatures(delivery.signatures)
    ):
        raise InvalidSignatureError
