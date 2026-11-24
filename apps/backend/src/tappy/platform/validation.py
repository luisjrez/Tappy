from http import HTTPStatus

from fastapi.exceptions import RequestValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

REPORTED_FIELDS = ("type", "loc", "msg")


def validation_error_response(_: Request, error: Exception) -> JSONResponse:
    issues = error.errors() if isinstance(error, RequestValidationError) else []
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
        content={
            "detail": [{field: issue[field] for field in REPORTED_FIELDS} for issue in issues]
        },
    )
