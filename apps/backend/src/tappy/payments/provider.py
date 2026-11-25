import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


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


class QrProvider(Protocol):
    @property
    def name(self) -> ProviderName: ...

    @property
    def simulated(self) -> bool: ...

    def create_qr(self, order: QrOrder) -> IssuedQr: ...
