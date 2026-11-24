import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class ProviderName(StrEnum):
    SIMULATED = "simulated"


class ProviderUnavailableError(Exception):
    pass


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
