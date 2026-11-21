from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tappy.identity.provisioning import IdentitySummary
from tappy.identity.sessions import UnauthorizedError, resolve_identity
from tappy.platform.dependencies import ClockDependency, SessionDependency

bearer = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_identity(
    session: SessionDependency,
    clock: ClockDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> IdentitySummary:
    if credentials is None:
        raise unauthorized()
    try:
        return resolve_identity(session, credentials.credentials, clock.now())
    except UnauthorizedError:
        raise unauthorized() from None


CurrentIdentity = Annotated[IdentitySummary, Depends(current_identity)]
