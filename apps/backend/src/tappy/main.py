from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from tappy.backoffice.admin import mount_admin
from tappy.identity import operators_router
from tappy.identity import router as identity_router
from tappy.merchants import router as merchants_router
from tappy.payments import router as webhooks_router
from tappy.payments.factory import provider_from
from tappy.payments.provider import QrProvider
from tappy.platform import health
from tappy.platform.clock import Clock, SystemClock
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.platform.validation import validation_error_response
from tappy.sales import exceptions_router, reports_router
from tappy.sales import router as sales_router


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
    app.add_exception_handler(RequestValidationError, validation_error_response)
    app.include_router(health.router)
    app.include_router(identity_router.router)
    app.include_router(operators_router.router)
    app.include_router(merchants_router.router)
    app.include_router(sales_router.router)
    app.include_router(reports_router.router)
    app.include_router(exceptions_router.router)
    app.include_router(webhooks_router.router)
    mount_admin(app, settings, database, app.state.clock)
    return app
