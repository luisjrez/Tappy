from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials

from tappy.identity.dependencies import CurrentIdentity, RecoveryDependency, bearer, unauthorized
from tappy.identity.recovery import RECOVERY_ACCEPTED, RecoverySubmission
from tappy.identity.schemas import (
    AcceptedResponse,
    IdentityResponse,
    LoginRequest,
    PasswordResetRequestBody,
    RefreshRequest,
    SessionResponse,
)
from tappy.identity.sessions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    IssuedSession,
    LoginCredentials,
    SessionPolicy,
    log_in,
    log_out,
    renew_session,
)
from tappy.platform.dependencies import (
    ClockDependency,
    DatabaseDependency,
    SessionDependency,
    SettingsDependency,
)
from tappy.platform.requests import client_origin

router = APIRouter(prefix="/auth", tags=["identity"])


def session_response(issued: IssuedSession) -> SessionResponse:
    return SessionResponse(
        access_token=issued.access_token,
        expires_at=issued.expires_at,
        refresh_token=issued.refresh_token,
        refresh_expires_at=issued.refresh_expires_at,
    )


@router.post(
    "/login",
    responses={HTTPStatus.UNAUTHORIZED: {"description": "Invalid email or password"}},
)
def login(
    payload: LoginRequest,
    db: SessionDependency,
    clock: ClockDependency,
    settings: SettingsDependency,
) -> SessionResponse:
    policy = SessionPolicy.from_settings(settings)
    try:
        credentials = LoginCredentials(payload.email, payload.password)
        issued = log_in(db, credentials, clock.now(), policy)
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=str(error)) from None
    return session_response(issued)


@router.post(
    "/refresh",
    responses={HTTPStatus.UNAUTHORIZED: {"description": "Invalid refresh token"}},
)
def refresh(
    payload: RefreshRequest,
    database: DatabaseDependency,
    clock: ClockDependency,
    settings: SettingsDependency,
) -> SessionResponse:
    policy = SessionPolicy.from_settings(settings)
    try:
        issued = renew_session(database, payload.refresh_token, clock.now(), policy)
    except InvalidRefreshTokenError as error:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=str(error)) from None
    return session_response(issued)


@router.post("/logout", status_code=HTTPStatus.NO_CONTENT)
def logout(
    db: SessionDependency,
    clock: ClockDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Response:
    if credentials is None:
        raise unauthorized()
    try:
        log_out(db, credentials.credentials, clock.now())
    except InvalidAccessTokenError:
        raise unauthorized() from None
    return Response(status_code=HTTPStatus.NO_CONTENT)


@router.post("/password-reset/request", status_code=HTTPStatus.ACCEPTED)
def request_reset(
    payload: PasswordResetRequestBody,
    request: Request,
    db: SessionDependency,
    clock: ClockDependency,
    recovery: RecoveryDependency,
) -> AcceptedResponse:
    recovery.submit(db, RecoverySubmission(payload.email, client_origin(request)), clock.now())
    return AcceptedResponse(detail=RECOVERY_ACCEPTED)


@router.get("/me", responses={HTTPStatus.UNAUTHORIZED: {"description": "Not authenticated"}})
def read_me(identity: CurrentIdentity) -> IdentityResponse:
    return IdentityResponse.model_validate(identity)
