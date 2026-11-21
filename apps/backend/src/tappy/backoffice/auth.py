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
    SessionPolicy,
    find_access,
    log_in,
    log_out,
    renew,
)
from tappy.platform.clock import Clock
from tappy.platform.database import Database

ACCESS_KEY = "access_token"
REFRESH_KEY = "refresh_token"


class PanelCredentials:
    def __init__(self, access_token: str, refresh_token: str) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token

    @classmethod
    def from_session(cls, request: Request) -> PanelCredentials | None:
        access_token = request.session.get(ACCESS_KEY)
        refresh_token = request.session.get(REFRESH_KEY)
        if not isinstance(access_token, str) or not isinstance(refresh_token, str):
            return None
        return cls(access_token, refresh_token)

    def store(self, request: Request) -> None:
        request.session[ACCESS_KEY] = self.access_token
        request.session[REFRESH_KEY] = self.refresh_token


class AdminAuthProvider(AuthProvider):
    def __init__(self, database: Database, clock: Clock, policy: SessionPolicy) -> None:
        super().__init__()
        self.database = database
        self.clock = clock
        self.policy = policy

    def start_session(self, email: str, password: str) -> PanelCredentials:
        with self.database.transaction() as db:
            attempt = LoginCredentials(email, password)
            issued = log_in(db, attempt, self.clock.now(), self.policy, Role.ADMIN)
        return PanelCredentials(issued.access_token, issued.refresh_token)

    def current_admin(self, credentials: PanelCredentials) -> tuple[str, PanelCredentials]:
        with self.database.transaction() as db:
            try:
                identity, _ = find_access(db, credentials.access_token, self.clock.now())
            except InvalidAccessTokenError:
                issued = renew(db, credentials.refresh_token, self.clock.now(), self.policy)
                credentials = PanelCredentials(issued.access_token, issued.refresh_token)
                identity, _ = find_access(db, credentials.access_token, self.clock.now())
            if identity.role is not Role.ADMIN:
                raise InvalidAccessTokenError
            return identity.email, credentials

    def end_session(self, credentials: PanelCredentials) -> None:
        with self.database.transaction() as db:
            log_out(db, credentials.access_token, self.clock.now())

    async def login(
        self, username: str, password: str, remember_me: bool, request: Request
    ) -> Response | None:
        try:
            credentials = await run_in_threadpool(self.start_session, username, password)
        except InvalidCredentialsError as error:
            raise LoginFailed(str(error)) from None
        credentials.store(request)
        return None

    async def authenticate(self, request: Request) -> AdminUser | None:
        credentials = PanelCredentials.from_session(request)
        if credentials is None:
            return None
        try:
            email, current = await run_in_threadpool(self.current_admin, credentials)
        except InvalidAccessTokenError, InvalidRefreshTokenError:
            request.session.clear()
            return None
        current.store(request)
        return AdminUser(username=email)

    async def logout(self, request: Request) -> Response | None:
        credentials = PanelCredentials.from_session(request)
        request.session.clear()
        if credentials is not None:
            try:
                await run_in_threadpool(self.end_session, credentials)
            except InvalidAccessTokenError:
                return None
        return None
