from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from tappy.identity.models import Role
from tappy.identity.provisioning import IdentitySummary
from tappy.identity.sessions import InvalidAccessTokenError, resolve_identity
from tappy.platform.dependencies import ClockDependency, SessionDependency

bearer = HTTPBearer(auto_error=False)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_identity(
    db: SessionDependency,
    clock: ClockDependency,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> IdentitySummary:
    if credentials is None:
        raise unauthorized()
    try:
        return resolve_identity(db, credentials.credentials, clock.now())
    except InvalidAccessTokenError:
        raise unauthorized() from None


CurrentIdentity = Annotated[IdentitySummary, Depends(current_identity)]


def current_admin(identity: CurrentIdentity) -> IdentitySummary:
    if identity.role is not Role.ADMIN:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Administrator role required")
    return identity


CurrentAdmin = Annotated[IdentitySummary, Depends(current_admin)]
