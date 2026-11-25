import secrets
from collections.abc import Callable
from datetime import timedelta

from tappy.payments.provider import IssuedQr, ProviderName, QrOrder, QrPayment


def simulated_identifier() -> str:
    return f"SIM-{secrets.token_hex(8).upper()}"


class SimulatedQrProvider:
    name = ProviderName.SIMULATED
    simulated = True

    def __init__(
        self,
        id_factory: Callable[[], str] = simulated_identifier,
        valid_for: timedelta | None = None,
    ) -> None:
        self.id_factory = id_factory
        self.valid_for = valid_for

    def create_qr(self, order: QrOrder) -> IssuedQr:
        payload = "|".join(
            [
                "SIMULATED-CODI-QR",
                f"ref={order.reference}",
                f"attempt={order.attempt_id}",
                f"amount_cents={order.amount_cents}",
                f"concept={order.concept or ''}",
            ]
        )
        return IssuedQr(self.id_factory(), payload, self.valid_for)

    def qr_payments(self, provider_request_id: str) -> list[QrPayment]:
        return []
