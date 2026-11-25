from datetime import timedelta

from tappy.payments.pey import PeyQrProvider, PeySettings
from tappy.payments.provider import QrProvider
from tappy.payments.simulator import SimulatedQrProvider
from tappy.platform.config import PEY_KEY_REQUIRED, Settings


def provider_from(settings: Settings) -> QrProvider:
    match settings.payment_provider:
        case "simulated":
            return SimulatedQrProvider(valid_for=timedelta(seconds=settings.qr_expiration_seconds))
        case "pey":
            return PeyQrProvider(pey_settings(settings))


def pey_settings(settings: Settings) -> PeySettings:
    if settings.pey_api_key is None:
        raise ValueError(PEY_KEY_REQUIRED)
    return PeySettings(
        settings.pey_base_url,
        settings.pey_api_key,
        settings.pey_timeout_seconds,
        timedelta(seconds=settings.qr_expiration_seconds),
    )
