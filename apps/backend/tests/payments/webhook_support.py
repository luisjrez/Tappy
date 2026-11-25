import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass

from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.platform.config import Settings
from tests.support import build_settings

SECRET_BYTES = b"synthetic-webhook-secret-for-tests-32b"
SECRET = "whsec_" + base64.b64encode(SECRET_BYTES).decode()
OTHER_SECRET = "whsec_" + base64.b64encode(b"another-synthetic-secret-0123456").decode()
EVENT = {
    "type": "codi.qr.payment_received",
    "amount": 300.1,
    "apiKeyId": "01HZZSYNTHETICAPIKEY0000",
    "bankAccountId": "01HZY3K8Q4N6V7W8X9Y0Z1A2B3",
    "codiQrId": "AB12CD34EF",
    "datePaid": 1795000000,
    "transactionId": "TX-SYNTHETIC-0001",
    "metadata": {"tappy_attempt_id": str(uuid.uuid4()), "tappy_reference": "MSPE6WGBSK"},
}
MAX_BODY = 256 * 1024


def settings_for(database_url: str) -> Settings:
    return Settings.model_validate(
        {**build_settings(database_url=database_url).model_dump(), "pey_webhook_secret": SECRET}
    )


def signature(secret: str, message_id: str, timestamp: str, body: bytes) -> str:
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{message_id}.{timestamp}.".encode() + body
    return "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()


@dataclass(frozen=True)
class Delivery:
    message_id: str = "msg_synthetic_0001"
    timestamp: int | None = None
    secret: str = SECRET
    signed_body: bytes | None = None


def deliver(client: TestClient, body: bytes, delivery: Delivery | None = None) -> Response:
    options = delivery or Delivery()
    stamp = str(int(time.time()) if options.timestamp is None else options.timestamp)
    headers = {
        "webhook-id": options.message_id,
        "webhook-timestamp": stamp,
        "webhook-signature": signature(
            options.secret, options.message_id, stamp, options.signed_body or body
        ),
        "content-type": "application/json",
    }
    return client.post("/webhooks/pey", content=body, headers=headers)


def encoded(event: object = EVENT) -> bytes:
    return json.dumps(event, separators=(",", ":")).encode()
