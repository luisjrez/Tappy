from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from tappy.platform.dependencies import SettingsDependency

router = APIRouter(tags=["platform"])


class HealthStatus(BaseModel):
    status: Literal["ok"]
    environment: str


@router.get("/health")
def read_health(settings: SettingsDependency) -> HealthStatus:
    return HealthStatus(status="ok", environment=settings.environment)
