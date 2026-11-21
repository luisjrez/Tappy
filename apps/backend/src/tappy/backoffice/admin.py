import logging

from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.base import BaseAdmin

from tappy.backoffice.auth import AdminAuthProvider
from tappy.identity.sessions import SessionPolicy
from tappy.platform.clock import Clock
from tappy.platform.config import Settings
from tappy.platform.database import Database

PANEL_COOKIE = "tappy_admin_session"


def mount_admin(app: FastAPI, settings: Settings, database: Database, clock: Clock) -> None:
    logging.getLogger("starlette_admin").setLevel(logging.ERROR)
    policy = SessionPolicy.from_settings(settings)
    secret = settings.secret_key.get_secret_value()
    admin = BaseAdmin(
        title="Tappy back office",
        base_url="/admin",
        auth_provider=AdminAuthProvider(database, clock, policy),
        secret_key=secret,
        middlewares=[
            Middleware(
                SessionMiddleware,
                secret_key=secret,
                session_cookie=PANEL_COOKIE,
                max_age=settings.session_max_lifetime_seconds,
                same_site="strict",
                https_only=settings.admin_secure_cookies,
            )
        ],
    )
    admin.mount_to(app)
