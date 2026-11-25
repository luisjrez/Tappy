from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.concurrency import run_in_threadpool

from tappy.payments.events import InvalidEventError, envelope_of, store_event
from tappy.payments.provider import ProviderName
from tappy.payments.webhooks import InvalidSignatureError, SignedDelivery, verify
from tappy.platform.clock import Clock
from tappy.platform.config import Settings
from tappy.platform.database import Database

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def limited_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, detail="Webhook body is too large")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, detail="Webhook body is too large")
    return bytes(body)


def persist(database: Database, delivery: SignedDelivery, clock: Clock) -> None:
    with database.transaction() as db:
        store_event(db, ProviderName.PEY, delivery, clock.now())


@router.post(
    "/pey",
    status_code=HTTPStatus.NO_CONTENT,
    responses={
        HTTPStatus.BAD_REQUEST: {"description": "Signed event with an invalid schema"},
        HTTPStatus.UNAUTHORIZED: {"description": "Invalid signature or timestamp"},
        HTTPStatus.CONTENT_TOO_LARGE: {"description": "Body over the configured limit"},
        HTTPStatus.SERVICE_UNAVAILABLE: {"description": "Not configured or storage unavailable"},
    },
)
async def receive_pey(request: Request) -> Response:
    settings: Settings = request.app.state.settings
    clock: Clock = request.app.state.clock
    database: Database = request.app.state.database
    if settings.pey_webhook_secret is None:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail="Webhooks are not configured")
    body = await limited_body(request, settings.webhook_max_body_bytes)
    delivery = SignedDelivery(
        request.headers.get("webhook-id", ""),
        request.headers.get("webhook-timestamp", ""),
        request.headers.get("webhook-signature", ""),
        body,
    )
    try:
        verify(
            settings.pey_webhook_secret, delivery, clock.now(), settings.webhook_tolerance_seconds
        )
        envelope_of(body)
    except InvalidSignatureError as error:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, detail=str(error)) from None
    except InvalidEventError as error:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail=str(error)) from None
    try:
        await run_in_threadpool(persist, database, delivery, clock)
    except OperationalError, InterfaceError:
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE, detail="Webhook storage is temporarily unavailable"
        ) from None
    return Response(status_code=HTTPStatus.NO_CONTENT)
