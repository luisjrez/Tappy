import secrets
from collections.abc import Callable

from tappy.payments.provider import IssuedQr, ProviderName, QrOrder, QrProvider
from tappy.platform.config import Settings


def simulated_identifier() -> str:
    return f"SIM-{secrets.token_hex(8).upper()}"


class SimulatedQrProvider:
    name = ProviderName.SIMULATED
    simulated = True

    def __init__(self, id_factory: Callable[[], str] = simulated_identifier) -> None:
        self.id_factory = id_factory

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
        return IssuedQr(self.id_factory(), payload)


def provider_from(settings: Settings) -> QrProvider:
    match settings.payment_provider:
        case "simulated":
            return SimulatedQrProvider()
