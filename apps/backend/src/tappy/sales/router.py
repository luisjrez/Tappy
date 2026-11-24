import uuid
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from tappy.identity.dependencies import CurrentIdentity, CurrentOperator
from tappy.merchants.errors import IssuanceBlockedError, MerchantNotFoundError
from tappy.platform.dependencies import ClockDependency, SessionDependency, SettingsDependency
from tappy.sales.errors import InvalidAmountError, InvalidConceptError, SaleNotFoundError
from tappy.sales.schemas import SaleCreateRequest, SaleResponse
from tappy.sales.service import SaleRequest, create_sale, read_sale

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post(
    "",
    status_code=HTTPStatus.CREATED,
    responses={
        HTTPStatus.NOT_FOUND: {"description": "Merchant not found or not accessible"},
        HTTPStatus.CONFLICT: {"description": "New charges are blocked"},
    },
)
def create(
    payload: SaleCreateRequest,
    actor: CurrentOperator,
    db: SessionDependency,
    clock: ClockDependency,
    settings: SettingsDependency,
) -> SaleResponse:
    request = SaleRequest(payload.merchant_id, payload.amount_cents, payload.concept)
    try:
        view = create_sale(db, actor, request, settings.sale_max_amount_cents, clock.now())
    except (InvalidAmountError, InvalidConceptError) as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail=str(error)) from None
    except MerchantNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    except IssuanceBlockedError as error:
        raise HTTPException(HTTPStatus.CONFLICT, detail=str(error)) from None
    return SaleResponse.model_validate(view)


@router.get("/{sale_id}", responses={HTTPStatus.NOT_FOUND: {"description": "Sale not found"}})
def read_one(sale_id: uuid.UUID, actor: CurrentIdentity, db: SessionDependency) -> SaleResponse:
    try:
        return SaleResponse.model_validate(read_sale(db, actor, sale_id))
    except SaleNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
