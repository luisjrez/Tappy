import uuid
from datetime import date
from http import HTTPStatus
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query

from tappy.identity.dependencies import CurrentIdentity
from tappy.merchants.errors import MerchantNotFoundError
from tappy.platform.dependencies import ClockDependency, SessionDependency, SettingsDependency
from tappy.sales.periods import BusinessDay, local_day
from tappy.sales.schemas import DailySummaryResponse
from tappy.sales.summaries import daily_summary

router = APIRouter(prefix="/merchants", tags=["reports"])


def requested_day(
    clock: ClockDependency,
    settings: SettingsDependency,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> BusinessDay:
    zone = ZoneInfo(settings.timezone)
    return BusinessDay(day or local_day(clock.now(), zone), zone)


@router.get(
    "/{merchant_id}/summary/daily",
    responses={HTTPStatus.NOT_FOUND: {"description": "Merchant not found or not accessible"}},
)
def read_daily_summary(
    merchant_id: uuid.UUID,
    actor: CurrentIdentity,
    db: SessionDependency,
    business_day: Annotated[BusinessDay, Depends(requested_day)],
) -> DailySummaryResponse:
    try:
        view = daily_summary(db, actor, merchant_id, business_day)
    except MerchantNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    return DailySummaryResponse.model_validate(view)
