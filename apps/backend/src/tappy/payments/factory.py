from tappy.payments.pey import PeyQrProvider, PeySettings
from tappy.payments.provider import QrProvider
from tappy.payments.simulator import SimulatedQrProvider
from tappy.platform.config import Settings


def provider_from(settings: Settings) -> QrProvider:
    match settings.payment_provider:
        case "simulated":
            return SimulatedQrProvider()
        case "pey":
            return PeyQrProvider(pey_settings(settings))


def pey_settings(settings: Settings) -> PeySettings:
    if settings.pey_api_key is None:
        raise ValueError("TAPPY_PEY_API_KEY is required when TAPPY_PAYMENT_PROVIDER is pey")
    return PeySettings(settings.pey_base_url, settings.pey_api_key, settings.pey_timeout_seconds)
