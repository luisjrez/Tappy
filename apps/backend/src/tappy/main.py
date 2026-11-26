from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from tappy.backoffice.admin import mount_admin
from tappy.identity import operators_router
from tappy.identity import router as identity_router
from tappy.identity.recovery import RecoveryService
from tappy.merchants import router as merchants_router
from tappy.payments import router as webhooks_router
from tappy.payments.factory import provider_from
from tappy.payments.provider import QrProvider
from tappy.platform import health
from tappy.platform.clock import Clock, SystemClock
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.platform.diagnostics import RequestReference
from tappy.platform.quota_responses import quota_exceeded_response
from tappy.platform.quotas import QuotaExceededError
from tappy.platform.validation import validation_error_response
from tappy.sales import exceptions_router, reports_router
from tappy.sales import router as sales_router

API_ROUTERS = (
    health.router,
    identity_router.router,
    operators_router.router,
    merchants_router.router,
    sales_router.router,
    reports_router.router,
    exceptions_router.router,
)


def create_app(
    settings: Settings, clock: Clock | None = None, qr_provider: QrProvider | None = None
) -> FastAPI:
    database = Database.from_settings(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            database.dispose()

    app = FastAPI(title="Tappy", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.clock = clock or SystemClock()
    app.state.qr_provider = qr_provider or provider_from(settings)
    app.state.recovery = RecoveryService.from_settings(settings)
    app.add_middleware(RequestReference)
    app.add_exception_handler(RequestValidationError, validation_error_response)
    app.add_exception_handler(QuotaExceededError, quota_exceeded_response)
    for router in API_ROUTERS:
        app.include_router(router, max_body_size=settings.api_max_body_bytes)
    app.include_router(webhooks_router.router)
    mount_admin(app, settings, database, app.state.clock, app.state.recovery)
    return app
