import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from httpx2 import Response

from tappy.identity.models import IdentityStatus, Role
from tappy.identity.provisioning import IdentitySummary
from tappy.main import create_app
from tappy.payments.provider import QrProvider
from tappy.platform.clock import Clock
from tappy.platform.config import Settings
from tappy.platform.quotas import QuotaPolicy
from tests.support import create_identity, scalar

ADMIN = "admin@tappy.example"
OPERATOR_A = "operadora.a@tappy.example"
OPERATOR_B = "operador.b@tappy.example"
PASSWORD = "credencial operativa 2026"
CLABE_A = "012180000123456782"
CLABE_B = "072180000999900017"
RECONFIGURED_AT = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
RECEIVER_A: dict[str, object] = {
    "provider_account_id": "bank-account-demo-a",
    "beneficiary_name": "Tienda Demo A SA de CV",
    "clabe": CLABE_A,
    "enabled": True,
}
BLOCKED_DISABLED = "The receiving account is disabled; new charges are blocked until it is enabled"
BLOCKED_MISSING = "No receiving account is configured; new charges are blocked"
REFERENCE = re.compile(r"[0-9A-HJKMNP-TV-Z]{10}")
DEFAULT_MAXIMUM = 100_000_000
AMOUNT = 30000
CONFIGURED_MAXIMUM = 50000
IDEMPOTENCY_HEADER = "Idempotency-Key"
AMPLE_QUOTA = QuotaPolicy(1000, timedelta(minutes=1))


def start_client(
    settings: Settings,
    database_url: str,
    qr_provider: QrProvider | None = None,
    clock: Clock | None = None,
) -> TestClient:
    create_identity(database_url, ADMIN, PASSWORD, role=Role.ADMIN)
    create_identity(database_url, OPERATOR_A, PASSWORD)
    create_identity(database_url, OPERATOR_B, PASSWORD)
    return app_client(settings, qr_provider, clock)


def app_client(
    settings: Settings, qr_provider: QrProvider | None = None, clock: Clock | None = None
) -> TestClient:
    return TestClient(create_app(settings, clock=clock, qr_provider=qr_provider))


def actor_of(client: TestClient, headers: dict[str, str]) -> IdentitySummary:
    me = client.get("/auth/me", headers=headers).json()
    return IdentitySummary(
        me["reference"], me["email"], Role(me["role"]), IdentityStatus(me["status"])
    )


def bearer(client: TestClient, email: str) -> dict[str, str]:
    tokens = client.post("/auth/login", json={"email": email, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def reference_of(database_url: str, email: str) -> str:
    return str(scalar(database_url, "SELECT id FROM identities WHERE email = :e", {"e": email}))


def merchant_of(client: TestClient, database_url: str, name: str, operator: str) -> str:
    admin = bearer(client, ADMIN)
    merchant_id: str = client.post("/merchants", json={"name": name}, headers=admin).json()["id"]
    client.post(
        f"/merchants/{merchant_id}/members",
        json={"operator_reference": reference_of(database_url, operator)},
        headers=admin,
    )
    return merchant_id


def ready_merchant(client: TestClient, database_url: str, name: str, operator: str) -> str:
    merchant_id = merchant_of(client, database_url, name, operator)
    configure(client, merchant_id)
    return merchant_id


def configure(client: TestClient, merchant_id: str, **changes: object) -> Response:
    payload = {**RECEIVER_A, **changes}
    return client.put(
        f"/merchants/{merchant_id}/receiver", json=payload, headers=bearer(client, ADMIN)
    )


def create_sale(
    client: TestClient, headers: dict[str, str], merchant_id: str, **fields: object
) -> Response:
    return create_sale_with_key(client, headers, merchant_id, str(uuid.uuid4()), **fields)


def create_sale_with_key(
    client: TestClient, headers: dict[str, str], merchant_id: str, key: str, **fields: object
) -> Response:
    return client.post(
        "/sales",
        json={"merchant_id": merchant_id, **fields},
        headers={**headers, IDEMPOTENCY_HEADER: key},
    )


def sale_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM sales")
