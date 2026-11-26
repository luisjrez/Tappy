from http import HTTPStatus

from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import JSONResponse

from tappy.platform.quotas import QuotaExceededError


class QuotaExceededResponse(BaseModel):
    detail: str
    retry_after_seconds: int


def quota_exceeded_response(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, QuotaExceededError):
        raise TypeError("Only quota errors are handled here")
    body = QuotaExceededResponse(detail=str(error), retry_after_seconds=error.retry_after)
    return JSONResponse(
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
        content=body.model_dump(),
        headers={"Retry-After": str(error.retry_after)},
    )
