import uuid
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from tappy.identity.dependencies import CurrentIdentity, CurrentOperator
from tappy.merchants.errors import IssuanceBlockedError, MerchantNotFoundError
from tappy.payments.dependencies import QrProviderDependency
from tappy.payments.provider import ProviderRejectedError
from tappy.platform.dependencies import (
    ClockDependency,
    DatabaseDependency,
    SessionDependency,
    SettingsDependency,
)
from tappy.sales.attempts import AttemptOutcome, AttemptRequest, request_attempt
from tappy.sales.errors import (
    ActiveAttemptError,
    InvalidAmountError,
    InvalidConceptError,
    NoReceptionError,
    ReceiverChangedError,
    SaleNotFoundError,
    SaleNotOpenError,
    UnverifiedAttemptError,
)
from tappy.sales.history import InvalidCursorError, sale_history
from tappy.sales.idempotency import KEY_PATTERN, IdempotencyConflictError
from tappy.sales.schemas import (
    AttemptCreateRequest,
    AttemptResponse,
    HistoryParams,
    HistoryResponse,
    ReceiptResponse,
    SaleCreateRequest,
    SaleResponse,
)
from tappy.sales.service import SaleRequest, create_sale, read_receipt, read_sale

router = APIRouter(prefix="/sales", tags=["sales"])
OUTCOME_STATUS = {
    AttemptOutcome.CREATED: HTTPStatus.CREATED,
    AttemptOutcome.REPLAYED: HTTPStatus.OK,
    AttemptOutcome.UNCERTAIN: HTTPStatus.ACCEPTED,
}


def sale_request(
    payload: SaleCreateRequest,
    idempotency_key: Annotated[str, Header(pattern=KEY_PATTERN)],
    actor: CurrentOperator,
) -> SaleRequest:
    return SaleRequest(
        actor, payload.merchant_id, payload.amount_cents, payload.concept, idempotency_key
    )


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.NOT_FOUND: {"description": "Merchant not found or not accessible"},
        HTTPStatus.OK: {
            "model": SaleResponse,
            "description": "Repeated request: the sale created with this key",
        },
        HTTPStatus.CONFLICT: {
            "description": "New charges are blocked or the key was used with other content"
        },
    },
)
def create(
    request: Annotated[SaleRequest, Depends(sale_request)],
    response: Response,
    db: SessionDependency,
    clock: ClockDependency,
    settings: SettingsDependency,
) -> SaleResponse:
    try:
        creation = create_sale(db, request, settings.sale_max_amount_cents, clock.now())
    except (InvalidAmountError, InvalidConceptError) as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail=str(error)) from None
    except MerchantNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    except (IssuanceBlockedError, IdempotencyConflictError) as error:
        raise HTTPException(HTTPStatus.CONFLICT, detail=str(error)) from None
    if creation.replayed:
        response.status_code = HTTPStatus.OK
    return SaleResponse.model_validate(creation.sale)


@router.get(
    "",
    responses={
        HTTPStatus.NOT_FOUND: {"description": "Merchant not found or not accessible"},
        HTTPStatus.UNPROCESSABLE_CONTENT: {"description": "Invalid filter, limit or cursor"},
    },
)
def read_history(
    params: Annotated[HistoryParams, Query()], actor: CurrentIdentity, db: SessionDependency
) -> HistoryResponse:
    try:
        return HistoryResponse.model_validate(sale_history(db, actor, params.to_query()))
    except MerchantNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    except InvalidCursorError as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail=str(error)) from None


@router.get("/{sale_id}", responses={HTTPStatus.NOT_FOUND: {"description": "Sale not found"}})
def read_one(
    sale_id: uuid.UUID, actor: CurrentIdentity, db: SessionDependency, clock: ClockDependency
) -> SaleResponse:
    try:
        return SaleResponse.model_validate(read_sale(db, actor, sale_id, clock.now()))
    except SaleNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None


@router.get(
    "/{sale_id}/receipt",
    responses={HTTPStatus.NOT_FOUND: {"description": "Sale not found or no confirmed reception"}},
)
def read_receipt_data(
    sale_id: uuid.UUID, actor: CurrentIdentity, db: SessionDependency
) -> ReceiptResponse:
    try:
        return ReceiptResponse.model_validate(read_receipt(db, actor, sale_id))
    except (SaleNotFoundError, NoReceptionError) as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None


def attempt_request(
    sale_id: uuid.UUID,
    payload: AttemptCreateRequest,
    idempotency_key: Annotated[str, Header(pattern=KEY_PATTERN)],
    actor: CurrentOperator,
) -> AttemptRequest:
    return AttemptRequest(actor, sale_id, payload.method, idempotency_key)


@router.post(
    "/{sale_id}/attempts",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.OK: {
            "model": AttemptResponse,
            "description": "Repeated request: the attempt reserved with this key",
        },
        HTTPStatus.NOT_FOUND: {"description": "Sale not found"},
        HTTPStatus.CONFLICT: {
            "description": (
                "Active attempt, unverified expired attempt, sale not open, charges blocked "
                "or key reused"
            )
        },
        HTTPStatus.BAD_GATEWAY: {"description": "QR provider rejected the request; attempt failed"},
        HTTPStatus.ACCEPTED: {
            "model": AttemptResponse,
            "description": "Provider outcome uncertain: the attempt is kept reconciling",
        },
    },
)
def reserve(
    request: Annotated[AttemptRequest, Depends(attempt_request)],
    response: Response,
    database: DatabaseDependency,
    clock: ClockDependency,
    provider: QrProviderDependency,
) -> AttemptResponse:
    try:
        reservation = request_attempt(database, request, provider, clock)
    except SaleNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    except ProviderRejectedError as error:
        raise HTTPException(
            HTTPStatus.BAD_GATEWAY,
            detail=f"The QR provider rejected the request ({error.code})",
        ) from None
    except (
        ActiveAttemptError,
        UnverifiedAttemptError,
        SaleNotOpenError,
        ReceiverChangedError,
        IssuanceBlockedError,
        IdempotencyConflictError,
    ) as error:
        raise HTTPException(HTTPStatus.CONFLICT, detail=str(error)) from None
    response.status_code = OUTCOME_STATUS[reservation.outcome]
    return AttemptResponse.model_validate(reservation.attempt)
