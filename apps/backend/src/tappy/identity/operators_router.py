import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from tappy.identity.dependencies import current_admin
from tappy.identity.errors import (
    IdentityAlreadyExistsError,
    IdentityNotFoundError,
    InvalidEmailError,
    PasswordPolicyError,
)
from tappy.identity.operators import (
    create_operator,
    deactivate_operator,
    find_operator,
    list_operators,
)
from tappy.identity.schemas import IdentityResponse, OperatorCreateRequest
from tappy.platform.dependencies import ClockDependency, SessionDependency

router = APIRouter(
    prefix="/operators",
    tags=["operators"],
    dependencies=[Depends(current_admin)],
    responses={
        HTTPStatus.UNAUTHORIZED: {"description": "Not authenticated"},
        HTTPStatus.FORBIDDEN: {"description": "Administrator role required"},
    },
)
NOT_FOUND: dict[int | str, dict[str, object]] = {
    HTTPStatus.NOT_FOUND: {"description": "Operator not found"}
}


def not_found(error: IdentityNotFoundError) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(error))


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.CONFLICT: {"description": "Email already registered"},
        HTTPStatus.UNPROCESSABLE_CONTENT: {"description": "Invalid email or password policy"},
    },
)
def create(payload: OperatorCreateRequest, db: SessionDependency) -> IdentityResponse:
    try:
        operator = create_operator(db, payload.email, payload.initial_password)
    except IdentityAlreadyExistsError as error:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(error)) from None
    except (InvalidEmailError, PasswordPolicyError) as error:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail=str(error)
        ) from None
    return IdentityResponse.model_validate(operator)


@router.get("")
def read_all(db: SessionDependency) -> list[IdentityResponse]:
    return [IdentityResponse.model_validate(operator) for operator in list_operators(db)]


@router.get("/{reference}", responses=NOT_FOUND)
def read_one(reference: uuid.UUID, db: SessionDependency) -> IdentityResponse:
    try:
        return IdentityResponse.model_validate(find_operator(db, reference))
    except IdentityNotFoundError as error:
        raise not_found(error) from None


@router.post("/{reference}/deactivate", responses=NOT_FOUND)
def deactivate(
    reference: uuid.UUID, db: SessionDependency, clock: ClockDependency
) -> IdentityResponse:
    try:
        return IdentityResponse.model_validate(deactivate_operator(db, reference, clock.now()))
    except IdentityNotFoundError as error:
        raise not_found(error) from None
