from fastapi import FastAPI

from tappy.platform import health
from tappy.platform.config import Settings


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Tappy")
    app.state.settings = settings
    app.include_router(health.router)
    return app
