import uuid
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException, Response

from tappy.identity.dependencies import CurrentIdentity, current_admin
from tappy.merchants.errors import (
    InvalidMerchantNameError,
    InvalidReceiverError,
    IssuanceBlockedError,
    MerchantNotFoundError,
    OperatorNotAssignableError,
    ReceiverAccountTakenError,
    ReceiverNotConfiguredError,
)
from tappy.merchants.receivers import (
    ReceiverSettings,
    configure_receiver,
    issuing_receiver,
    read_receiver,
)
from tappy.merchants.schemas import (
    IssuanceCheckRequest,
    MembershipRequest,
    MerchantCreateRequest,
    MerchantResponse,
    ReceiverRequest,
    ReceiverResponse,
)
from tappy.merchants.service import (
    assign_operator,
    create_merchant,
    list_merchants,
    read_merchant,
)
from tappy.platform.dependencies import ClockDependency, SessionDependency

router = APIRouter(prefix="/merchants", tags=["merchants"])
ADMIN_ONLY = [Depends(current_admin)]
NOT_FOUND: dict[int | str, dict[str, object]] = {
    HTTPStatus.NOT_FOUND: {"description": "Merchant not found or not accessible"}
}


def not_found() -> HTTPException:
    return HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Merchant not found")


def unprocessable(error: Exception) -> HTTPException:
    return HTTPException(status_code=HTTPStatus.UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("")
def read_all(actor: CurrentIdentity, db: SessionDependency) -> list[MerchantResponse]:
    return [MerchantResponse.model_validate(view) for view in list_merchants(db, actor)]


@router.get("/{merchant_id}", responses=NOT_FOUND)
def read_one(
    merchant_id: uuid.UUID, actor: CurrentIdentity, db: SessionDependency
) -> MerchantResponse:
    try:
        return MerchantResponse.model_validate(read_merchant(db, actor, merchant_id))
    except MerchantNotFoundError:
        raise not_found() from None


@router.post("", status_code=HTTPStatus.CREATED, dependencies=ADMIN_ONLY)
def create(
    payload: MerchantCreateRequest, db: SessionDependency, clock: ClockDependency
) -> MerchantResponse:
    try:
        return MerchantResponse.model_validate(create_merchant(db, payload.name, clock.now()))
    except InvalidMerchantNameError as error:
        raise unprocessable(error) from None


@router.post(
    "/{merchant_id}/members",
    status_code=HTTPStatus.CREATED,
    dependencies=ADMIN_ONLY,
    responses={**NOT_FOUND, HTTPStatus.OK: {"description": "Membership already existed"}},
)
def assign(
    merchant_id: uuid.UUID,
    payload: MembershipRequest,
    response: Response,
    db: SessionDependency,
    clock: ClockDependency,
) -> MerchantResponse:
    try:
        result = assign_operator(db, merchant_id, payload.operator_reference, clock.now())
    except MerchantNotFoundError:
        raise not_found() from None
    except OperatorNotAssignableError as error:
        raise unprocessable(error) from None
    if not result.created:
        response.status_code = HTTPStatus.OK
    return MerchantResponse.model_validate(result.merchant)


@router.put("/{merchant_id}/receiver", dependencies=ADMIN_ONLY, responses=NOT_FOUND)
def configure(
    merchant_id: uuid.UUID,
    payload: ReceiverRequest,
    db: SessionDependency,
    clock: ClockDependency,
) -> ReceiverResponse:
    settings = ReceiverSettings(
        provider_account_id=payload.provider_account_id,
        beneficiary_name=payload.beneficiary_name,
        clabe=payload.clabe.get_secret_value(),
        enabled=payload.enabled,
    )
    try:
        view = configure_receiver(db, merchant_id, settings, clock.now())
    except MerchantNotFoundError:
        raise not_found() from None
    except InvalidReceiverError as error:
        raise unprocessable(error) from None
    except ReceiverAccountTakenError as error:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(error)) from None
    return ReceiverResponse.model_validate(view)


@router.get("/{merchant_id}/receiver", responses=NOT_FOUND)
def read_receiver_of(
    merchant_id: uuid.UUID, actor: CurrentIdentity, db: SessionDependency
) -> ReceiverResponse:
    try:
        return ReceiverResponse.model_validate(read_receiver(db, actor, merchant_id))
    except MerchantNotFoundError:
        raise not_found() from None
    except ReceiverNotConfiguredError as error:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(error)) from None


@router.post(
    "/{merchant_id}/issuance-check",
    responses={**NOT_FOUND, HTTPStatus.CONFLICT: {"description": "New charges are blocked"}},
)
def check_issuance(
    merchant_id: uuid.UUID,
    payload: IssuanceCheckRequest,
    actor: CurrentIdentity,
    db: SessionDependency,
) -> ReceiverResponse:
    try:
        return ReceiverResponse.model_validate(issuing_receiver(db, actor, merchant_id))
    except MerchantNotFoundError:
        raise not_found() from None
    except IssuanceBlockedError as error:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail=str(error)) from None
