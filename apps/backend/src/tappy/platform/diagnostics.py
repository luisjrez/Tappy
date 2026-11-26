import logging
import re
import uuid
from contextvars import ContextVar
from typing import TextIO

from sqlalchemy.engine import make_url
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tappy.platform.config import Settings
from tappy.platform.redaction import redact

HEADER = "X-Request-ID"
SAFE_REFERENCE = re.compile(r"[A-Za-z0-9_-]{8,64}")
HANDLER_NAME = "tappy"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s [%(reference)s] %(message)s"
NO_REFERENCE = "-"

current_reference: ContextVar[str] = ContextVar("current_reference", default=NO_REFERENCE)
logger = logging.getLogger(__name__)


def reference_from(scope: Scope) -> str:
    offered = Headers(scope=scope).get(HEADER, "")
    return offered if SAFE_REFERENCE.fullmatch(offered) else uuid.uuid4().hex


def route_of(scope: Scope) -> str:
    return str(getattr(scope.get("route"), "path", "unmatched route"))


class RequestReference:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        reference = reference_from(scope)
        token = current_reference.set(reference)
        started = False

        async def send_with_reference(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)[HEADER] = reference
            await send(message)

        try:
            await self.app(scope, receive, send_with_reference)
        except Exception:
            logger.exception("Unhandled error in %s %s", scope["method"], route_of(scope))
            if started:
                raise
            response = JSONResponse(
                {"detail": "Internal server error", "reference": reference},
                status_code=500,
                headers={HEADER: reference},
            )
            await response(scope, receive, send)
        finally:
            current_reference.reset(token)


class ReferenceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.reference = current_reference.get()
        return True


class RedactingFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...]) -> None:
        super().__init__(LOG_FORMAT)
        self.secrets = secrets

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record), self.secrets)


def configured_secrets(settings: Settings) -> tuple[str, ...]:
    values = [settings.secret_key, settings.pey_api_key, settings.pey_webhook_secret]
    revealed = [value.get_secret_value() for value in values if value]
    password = make_url(settings.database_url.get_secret_value()).password
    bare = [secret.removeprefix("whsec_") for secret in revealed]
    return tuple(secret for secret in dict.fromkeys([*revealed, *bare, password]) if secret)


def configure_logging(settings: Settings, stream: TextIO | None = None) -> logging.Handler:
    root = logging.getLogger()
    for existing in [handler for handler in root.handlers if handler.get_name() == HANDLER_NAME]:
        root.removeHandler(existing)
    handler = logging.StreamHandler(stream)
    handler.set_name(HANDLER_NAME)
    handler.setFormatter(RedactingFormatter(configured_secrets(settings)))
    handler.addFilter(ReferenceFilter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return handler
