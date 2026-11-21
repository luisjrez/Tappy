from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from tappy.backoffice.admin import mount_admin
from tappy.identity import operators_router, reset_page
from tappy.identity import router as identity_router
from tappy.identity.recovery import RecoveryService
from tappy.platform import health
from tappy.platform.clock import Clock, SystemClock
from tappy.platform.config import Settings
from tappy.platform.database import Database


def create_app(settings: Settings, clock: Clock | None = None) -> FastAPI:
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
    app.state.recovery = RecoveryService.from_settings(settings)
    app.include_router(health.router)
    app.include_router(identity_router.router)
    app.include_router(operators_router.router)
    app.include_router(reset_page.router)
    mount_admin(app, settings, database, app.state.clock, app.state.recovery)
    return app
