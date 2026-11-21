from datetime import timedelta
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from tappy.identity.dependencies import CurrentIdentity
from tappy.identity.schemas import IdentityResponse, LoginRequest, SessionResponse
from tappy.identity.sessions import AuthenticationError, log_in
from tappy.platform.dependencies import ClockDependency, SessionDependency, SettingsDependency

router = APIRouter(prefix="/auth", tags=["identity"])


@router.post(
    "/login",
    responses={HTTPStatus.UNAUTHORIZED: {"description": "Invalid email or password"}},
)
def login(
    payload: LoginRequest,
    session: SessionDependency,
    clock: ClockDependency,
    settings: SettingsDependency,
) -> SessionResponse:
    lifetime = timedelta(seconds=settings.access_token_ttl_seconds)
    try:
        issued = log_in(session, payload.email, payload.password, clock.now(), lifetime)
    except AuthenticationError as error:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail=str(error)) from None
    return SessionResponse(access_token=issued.access_token, expires_at=issued.expires_at)


@router.get("/me", responses={HTTPStatus.UNAUTHORIZED: {"description": "Not authenticated"}})
def read_me(identity: CurrentIdentity) -> IdentityResponse:
    return IdentityResponse(
        reference=identity.reference,
        email=identity.email,
        role=identity.role,
        status=identity.status,
    )
