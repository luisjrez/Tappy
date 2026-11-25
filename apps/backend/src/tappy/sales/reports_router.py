import uuid
from datetime import date
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from tappy.identity.dependencies import CurrentIdentity
from tappy.merchants.errors import MerchantNotFoundError
from tappy.platform.dependencies import ClockDependency, SessionDependency, SettingsDependency
from tappy.sales.periods import BusinessPeriod, PeriodKind
from tappy.sales.schemas import DailySummaryResponse, PeriodParams, PeriodSummaryResponse
from tappy.sales.summaries import daily_summary, period_summary

router = APIRouter(prefix="/merchants", tags=["reports"])
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {"description": "Merchant not found or not accessible"}
}


def requested_day(
    clock: ClockDependency,
    settings: SettingsDependency,
    day: Annotated[date | None, Query(alias="date")] = None,
) -> BusinessPeriod:
    if day is None:
        return BusinessPeriod.today(PeriodKind.DAY, clock.now(), settings.zone)
    return BusinessPeriod.containing(PeriodKind.DAY, day, settings.zone)


def requested_period(
    params: Annotated[PeriodParams, Query()],
    clock: ClockDependency,
    settings: SettingsDependency,
) -> BusinessPeriod:
    if params.day is None:
        return BusinessPeriod.today(params.period, clock.now(), settings.zone)
    return BusinessPeriod.containing(params.period, params.day, settings.zone)


@router.get("/{merchant_id}/summary/daily", responses=NOT_FOUND)
def read_daily_summary(
    merchant_id: uuid.UUID,
    actor: CurrentIdentity,
    db: SessionDependency,
    period: Annotated[BusinessPeriod, Depends(requested_day)],
) -> DailySummaryResponse:
    try:
        return DailySummaryResponse.model_validate(daily_summary(db, actor, merchant_id, period))
    except MerchantNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None


@router.get("/{merchant_id}/summary", responses=NOT_FOUND)
def read_period_summary(
    merchant_id: uuid.UUID,
    actor: CurrentIdentity,
    db: SessionDependency,
    period: Annotated[BusinessPeriod, Depends(requested_period)],
) -> PeriodSummaryResponse:
    try:
        return PeriodSummaryResponse.model_validate(period_summary(db, actor, merchant_id, period))
    except MerchantNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
