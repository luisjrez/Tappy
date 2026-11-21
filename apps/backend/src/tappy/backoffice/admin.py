import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.base import BaseAdmin

from tappy.backoffice.auth import AdminAuthProvider
from tappy.backoffice.operators import OperatorsView
from tappy.identity.passwords import PasswordPolicy
from tappy.identity.recovery import RecoveryService
from tappy.identity.sessions import SessionPolicy
from tappy.platform.clock import Clock
from tappy.platform.config import Settings
from tappy.platform.database import Database

PANEL_COOKIE = "tappy_admin_session"
ADMIN_BASE_URL = "/admin"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def mount_admin(
    app: FastAPI, settings: Settings, database: Database, clock: Clock, recovery: RecoveryService
) -> None:
    logging.getLogger("starlette_admin").setLevel(logging.ERROR)
    policy = SessionPolicy.from_settings(settings)
    secret = settings.secret_key.get_secret_value()
    admin = BaseAdmin(
        title="Tappy back office",
        base_url=ADMIN_BASE_URL,
        templates_dir=str(TEMPLATES_DIR),
        auth_provider=AdminAuthProvider(database, clock, policy, recovery),
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
    admin.add_view(
        OperatorsView(database, clock, ADMIN_BASE_URL, PasswordPolicy.from_settings(settings))
    )
    admin.mount_to(app)
