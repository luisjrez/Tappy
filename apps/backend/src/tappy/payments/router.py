from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.concurrency import run_in_threadpool

from tappy.payments.events import (
    InvalidEventError,
    ReceivedEvent,
    StoreOutcome,
    envelope_of,
    store_event,
)
from tappy.payments.provider import ProviderName
from tappy.payments.webhooks import InvalidSignatureError, SignedDelivery, verify
from tappy.platform.clock import Clock
from tappy.platform.database import Database
from tappy.platform.dependencies import ClockDependency, DatabaseDependency, SettingsDependency
from tappy.sales.receptions import process_stored

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
TOO_LARGE = "Webhook body is too large"


async def limited_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, detail=TOO_LARGE)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(HTTPStatus.CONTENT_TOO_LARGE, detail=TOO_LARGE)
    return bytes(body)


def persist(database: Database, event: ReceivedEvent, clock: Clock) -> StoreOutcome:
    with database.transaction() as db:
        return store_event(db, event, clock.now())


def apply_stored(database: Database, event: ReceivedEvent, clock: Clock) -> None:
    process_stored(database, event, clock)


def signed_delivery(request: Request, body: bytes) -> SignedDelivery:
    return SignedDelivery(
        request.headers.get("webhook-id", ""),
        request.headers.get("webhook-timestamp", ""),
        request.headers.get("webhook-signature", ""),
        body,
    )


@router.post(
    "/pey",
    status_code=HTTPStatus.NO_CONTENT,
    responses={
        HTTPStatus.BAD_REQUEST: {"description": "Signed event with an invalid schema"},
        HTTPStatus.UNAUTHORIZED: {"description": "Invalid signature, timestamp or event id"},
        HTTPStatus.CONTENT_TOO_LARGE: {"description": "Body over the configured limit"},
        HTTPStatus.SERVICE_UNAVAILABLE: {"description": "Not configured or storage unavailable"},
    },
)
async def receive_pey(
    request: Request,
    settings: SettingsDependency,
    clock: ClockDependency,
    database: DatabaseDependency,
) -> Response:
    secret = settings.pey_webhook_secret
    if secret is None:
        raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, detail="Webhooks are not configured")
    delivery = signed_delivery(
        request, await limited_body(request, settings.webhook_max_body_bytes)
    )
    try:
        signed_at = verify(secret, delivery, clock.now(), settings.webhook_tolerance_seconds)
        envelope = envelope_of(delivery.body)
    except InvalidSignatureError as error:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, detail=str(error)) from None
    except InvalidEventError as error:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail=str(error)) from None
    event = ReceivedEvent(
        provider=ProviderName.PEY,
        environment=settings.environment,
        message_id=delivery.message_id,
        event_type=envelope.type,
        body=delivery.body,
        signed_at=signed_at,
    )
    try:
        stored = await run_in_threadpool(persist, database, event, clock)
    except OperationalError, InterfaceError:
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE, detail="Webhook storage is temporarily unavailable"
        ) from None
    if stored is not StoreOutcome.CONFLICT:
        await run_in_threadpool(apply_stored, database, event, clock)
    return Response(status_code=HTTPStatus.NO_CONTENT)
