import uuid
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from tappy.identity.dependencies import CurrentAdmin
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

router = APIRouter(prefix="/operators", tags=["operators"])
NOT_FOUND: dict[int | str, dict[str, object]] = {
    HTTPStatus.NOT_FOUND: {"description": "Operator not found"}
}


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.CONFLICT: {"description": "Email already registered"},
        HTTPStatus.UNPROCESSABLE_CONTENT: {"description": "Invalid email or password policy"},
    },
)
def create(
    payload: OperatorCreateRequest, admin: CurrentAdmin, db: SessionDependency
) -> IdentityResponse:
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
def read_all(admin: CurrentAdmin, db: SessionDependency) -> list[IdentityResponse]:
    return [IdentityResponse.model_validate(operator) for operator in list_operators(db)]


@router.get("/{reference}", responses=NOT_FOUND)
def read_one(reference: uuid.UUID, admin: CurrentAdmin, db: SessionDependency) -> IdentityResponse:
    try:
        return IdentityResponse.model_validate(find_operator(db, reference))
    except IdentityNotFoundError as error:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(error)) from None


@router.post("/{reference}/deactivate", responses=NOT_FOUND)
def deactivate(
    reference: uuid.UUID, admin: CurrentAdmin, db: SessionDependency, clock: ClockDependency
) -> IdentityResponse:
    try:
        return IdentityResponse.model_validate(deactivate_operator(db, reference, clock.now()))
    except IdentityNotFoundError as error:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(error)) from None
