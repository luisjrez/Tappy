import uuid
from typing import Any

import httpx2
from fastapi.testclient import TestClient

from tappy.platform.config import Settings
from tappy.platform.phones import phone_list
from tests.payments.pey_support import FakePey
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    bearer,
    create_sale,
    ready_merchant,
)
from tests.support import VALID_SECRET, build_settings

CONSENTED = "5512345678"
OTHER_CONSENTED = "5587650000"
NOT_CONSENTED = "5599990000"
ALLOWED = f"{CONSENTED},{OTHER_CONSENTED}"


def phone_settings(database_url: str, allowed: str = ALLOWED) -> Settings:
    return build_settings(database_url=database_url).model_copy(
        update={"phone_request_numbers": phone_list(allowed)}
    )


def demo_list_settings(environment: str, numbers: str, provider: str = "simulated") -> Settings:
    return Settings.model_validate(
        {
            "environment": environment,
            "secret_key": VALID_SECRET,
            "database_url": "postgresql+psycopg://user:password@127.0.0.1/db",
            "payment_provider": provider,
            "pey_api_key": "test-pey-secret-0123456789abcdef",
            "phone_request_numbers": numbers,
        }
    )


def open_sale(client: TestClient, database_url: str) -> tuple[dict[str, Any], dict[str, str]]:
    merchant = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator = bearer(client, OPERATOR_A)
    return create_sale(client, operator, merchant, amount_cents=AMOUNT).json(), operator


def request_phone(
    client: TestClient,
    headers: dict[str, str],
    sale_id: str,
    payload: dict[str, object],
    key: str | None = None,
) -> httpx2.Response:
    return client.post(
        f"/sales/{sale_id}/attempts",
        json=payload,
        headers={**headers, IDEMPOTENCY_HEADER: key or str(uuid.uuid4())},
    )


def posted(fake: FakePey) -> list[httpx2.Request]:
    return [request for request in fake.requests if request.method == "POST"]
