from contextlib import suppress

from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import LoginFailed

from tappy.identity.models import Role
from tappy.identity.sessions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    LoginCredentials,
    RefreshTokenReuseError,
    ResumedSession,
    RoleNotAllowedError,
    SessionPolicy,
    SessionTokens,
    log_in,
    log_out,
    resume_session,
)
from tappy.platform.clock import Clock
from tappy.platform.database import Database

ACCESS_KEY = "access_token"
REFRESH_KEY = "refresh_token"


def stored_tokens(request: Request) -> SessionTokens | None:
    access_token = request.session.get(ACCESS_KEY)
    refresh_token = request.session.get(REFRESH_KEY)
    if not isinstance(access_token, str) or not isinstance(refresh_token, str):
        return None
    return SessionTokens(access_token, refresh_token)


def store_tokens(request: Request, tokens: SessionTokens) -> None:
    request.session[ACCESS_KEY] = tokens.access_token
    request.session[REFRESH_KEY] = tokens.refresh_token


class AdminAuthProvider(AuthProvider):
    def __init__(self, database: Database, clock: Clock, policy: SessionPolicy) -> None:
        super().__init__()
        self.database = database
        self.clock = clock
        self.policy = policy

    def start_session(self, email: str, password: str) -> SessionTokens:
        with self.database.transaction() as db:
            attempt = LoginCredentials(email, password)
            issued = log_in(db, attempt, self.clock.now(), self.policy, Role.ADMIN)
        return issued.tokens

    def resume(self, tokens: SessionTokens) -> ResumedSession:
        return resume_session(self.database, tokens, self.clock.now(), self.policy, Role.ADMIN)

    def end_session(self, tokens: SessionTokens) -> None:
        with self.database.transaction() as db:
            log_out(db, tokens.access_token, self.clock.now())

    async def login(
        self, username: str, password: str, remember_me: bool, request: Request
    ) -> Response | None:
        try:
            tokens = await run_in_threadpool(self.start_session, username, password)
        except InvalidCredentialsError as error:
            raise LoginFailed(str(error)) from None
        store_tokens(request, tokens)
        return None

    async def authenticate(self, request: Request) -> AdminUser | None:
        tokens = stored_tokens(request)
        if tokens is None:
            return None
        try:
            resumed = await run_in_threadpool(self.resume, tokens)
        except RoleNotAllowedError:
            request.session.clear()
            with suppress(InvalidAccessTokenError):
                await run_in_threadpool(self.end_session, tokens)
            return None
        except InvalidAccessTokenError, RefreshTokenReuseError:
            request.session.clear()
            return None
        except InvalidRefreshTokenError:
            return None
        store_tokens(request, resumed.tokens)
        return AdminUser(username=resumed.identity.email)

    async def logout(self, request: Request) -> Response | None:
        tokens = stored_tokens(request)
        request.session.clear()
        if tokens is not None:
            with suppress(InvalidAccessTokenError):
                await run_in_threadpool(self.end_session, tokens)
        return None
