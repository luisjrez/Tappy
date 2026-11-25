import uuid
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException

from tappy.identity.dependencies import CurrentAdmin
from tappy.platform.dependencies import ClockDependency, SessionDependency
from tappy.sales.errors import ExceptionNotFoundError, InvalidNoteError, NothingToReconcileError
from tappy.sales.exception_review import add_note, read_exception, request_reconciliation
from tappy.sales.schemas import (
    ExceptionDetailResponse,
    NoteRequest,
    NoteResponse,
    RequestedReconciliationResponse,
)

router = APIRouter(prefix="/exceptions", tags=["incidents"])
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {"description": "Incident not found"}
}


@router.get("/{exception_id}", responses=NOT_FOUND)
def read_one(
    exception_id: uuid.UUID, _admin: CurrentAdmin, db: SessionDependency
) -> ExceptionDetailResponse:
    try:
        return ExceptionDetailResponse.model_validate(read_exception(db, exception_id))
    except ExceptionNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None


@router.post("/{exception_id}/notes", status_code=HTTPStatus.CREATED, responses=NOT_FOUND)
def write_note(
    exception_id: uuid.UUID,
    payload: NoteRequest,
    admin: CurrentAdmin,
    db: SessionDependency,
    clock: ClockDependency,
) -> NoteResponse:
    try:
        return NoteResponse.model_validate(
            add_note(db, admin, exception_id, payload.text, clock.now())
        )
    except ExceptionNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    except InvalidNoteError as error:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail=str(error)) from None


@router.post(
    "/{exception_id}/reconciliation",
    status_code=HTTPStatus.ACCEPTED,
    responses={
        **NOT_FOUND,
        HTTPStatus.CONFLICT: {"description": "The incident has no QR attempt"},
    },
)
def request_review(
    exception_id: uuid.UUID, admin: CurrentAdmin, db: SessionDependency, clock: ClockDependency
) -> RequestedReconciliationResponse:
    try:
        requested = request_reconciliation(db, admin, exception_id, clock.now())
    except ExceptionNotFoundError as error:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail=str(error)) from None
    except NothingToReconcileError as error:
        raise HTTPException(HTTPStatus.CONFLICT, detail=str(error)) from None
    return RequestedReconciliationResponse.model_validate(requested)
