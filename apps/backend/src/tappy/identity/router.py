from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials

from tappy.identity.dependencies import CurrentIdentity, bearer, unauthorized
from tappy.identity.schemas import (
    IdentityResponse,
    LoginRequest,
    RefreshRequest,
    SessionResponse,
)
from tappy.identity.sessions import (
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    IssuedSession,
    LoginCredentials,
    RefreshTokenReuseError,
    SessionPolicy,
    log_in,
    log_out,
    renew,
    revoke_family,
)
from tappy.platform.dependencies import (
    ClockDependency,
    DatabaseDependency,
    SessionDependency,
    SettingsDependency,
)

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
    db: SessionDependency,
    database: DatabaseDependency,
    clock: ClockDependency,
    settings: SettingsDependency,
) -> SessionResponse:
    policy = SessionPolicy.from_settings(settings)
    try:
        issued = renew(db, payload.refresh_token, clock.now(), policy)
    except RefreshTokenReuseError as reuse:
        with database.transaction() as revocation:
            revoke_family(revocation, reuse.family_id, clock.now())
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=str(reuse)) from None
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


@router.get("/me", responses={HTTPStatus.UNAUTHORIZED: {"description": "Not authenticated"}})
def read_me(identity: CurrentIdentity) -> IdentityResponse:
    return IdentityResponse.model_validate(identity)
