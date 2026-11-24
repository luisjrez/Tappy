from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel

from tappy.platform.dependencies import DatabaseDependency, SettingsDependency

router = APIRouter(tags=["platform"])


class HealthStatus(BaseModel):
    status: Literal["ok"]
    environment: str


class ReadinessStatus(BaseModel):
    status: Literal["ready", "unavailable"]


@router.get("/health")
def read_health(settings: SettingsDependency) -> HealthStatus:
    return HealthStatus(status="ok", environment=settings.environment)


@router.get(
    "/ready",
    responses={HTTPStatus.SERVICE_UNAVAILABLE: {"model": ReadinessStatus}},
)
def read_readiness(database: DatabaseDependency, response: Response) -> ReadinessStatus:
    if database.is_ready():
        return ReadinessStatus(status="ready")
    response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
    return ReadinessStatus(status="unavailable")
