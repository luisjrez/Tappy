import hashlib
import hmac
import json
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tappy.platform.clock import SystemClock
from tappy.platform.config import Settings
from tappy.platform.database import Database
from tappy.platform.phones import (
    PhoneNumberError,
    normalized_phone,
    phone_fingerprint,
    phone_list,
)
from tappy.sales.idempotency import digest_of
from tappy.sales.reconciliation import ReconciliationResult, reconcile_attempt
from tests.payments.pey_support import PUSH_CREATED, PUSH_FIXTURE, FakePey
from tests.sales.support import (
    AMOUNT,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
    start_client,
)
from tests.support import VALID_SECRET, build_settings, execute, run_sales, scalar

CONSENTED = "5512345678"
OTHER_CONSENTED = "5587650000"
NOT_CONSENTED = "5599990000"
ALLOWED = f"{CONSENTED},{OTHER_CONSENTED}"
FULLWIDTH_DIGITS = "".join(chr(0xFF10 + int(digit)) for digit in CONSENTED)
EXPIRATION_MINIMUM = PUSH_FIXTURE["request_schema"]["properties"]["expiration"]["minimum"]


def phone_settings(database_url: str, allowed: str = ALLOWED) -> Settings:
    return build_settings(database_url=database_url).model_copy(
        update={"phone_request_numbers": phone_list(allowed)}
    )


@pytest.fixture
def fake() -> FakePey:
    return FakePey(status=200, body=PUSH_CREATED)


@pytest.fixture
def client(migrated_database_url: str, fake: FakePey) -> Iterator[TestClient]:
    settings = phone_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, fake.provider()) as started:
        yield started


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


def attempt_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM payment_attempts")


def test_a_consented_number_creates_a_pending_request_that_keeps_the_provider_ids(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator = open_sale(client, migrated_database_url)

    created = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": "55 1234 5678"}
    )
    body = created.json()
    read = client.get(f"/sales/{sale['id']}", headers=operator).json()
    sent = json.loads(posted(fake)[0].content)

    assert created.status_code == HTTPStatus.CREATED
    assert body["method"] == "phone"
    assert body["status"] == "pending"
    assert body["next_action"] == "wait_for_payment"
    assert body["provider_request_id"] == PUSH_CREATED["transactionId"]
    assert body["provider_folio"] == PUSH_CREATED["codiId"]
    assert body["sale_reference"] == sale["reference"]
    assert body["payer_phone"] == "******5678"
    assert body["qr_payload"] is None
    assert body["expires_at"] is not None
    assert not [field for field in body if "deliver" in field or "read" in field]
    assert read["attempts"] == [body]
    assert posted(fake)[0].url.path == "/codi/pn"
    assert sent["phoneNumber"] == CONSENTED
    assert sent["amount"] == AMOUNT / 100
    assert sent["bankAccountId"] == RECEIVER_A["provider_account_id"]
    assert sent["expiration"] >= EXPIRATION_MINIMUM
    assert sent["metadata"] == {
        "tappy_attempt_id": body["id"],
        "tappy_reference": sale["reference"],
    }
    assert set(sent) <= set(PUSH_FIXTURE["request_schema"]["properties"])
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM payment_attempts "
            "WHERE row_to_json(payment_attempts)::text LIKE :n",
            {"n": f"%{CONSENTED}%"},
        )
        == 0
    )


@pytest.mark.parametrize(
    "number", ["551234567", "55123456789", "55-1234-567a", "+1 555 123 4567", "", FULLWIDTH_DIGITS]
)
def test_an_invalid_number_is_rejected_without_an_attempt_or_a_provider_request(
    client: TestClient, migrated_database_url: str, fake: FakePey, number: str
) -> None:
    sale, operator = open_sale(client, migrated_database_url)

    response = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": number}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert attempt_count(migrated_database_url) == 0
    assert fake.requests == []


@pytest.mark.parametrize(
    "payload",
    [
        {"method": "phone"},
        {"method": "phone", "phone_number": None},
        {"method": "qr", "phone_number": CONSENTED},
    ],
)
def test_the_number_is_required_for_phone_requests_and_refused_for_qr(
    client: TestClient, migrated_database_url: str, fake: FakePey, payload: dict[str, object]
) -> None:
    sale, operator = open_sale(client, migrated_database_url)

    response = request_phone(client, operator, sale["id"], payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert attempt_count(migrated_database_url) == 0
    assert fake.requests == []


def test_a_number_outside_the_demo_list_is_refused_without_a_provider_request(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator = open_sale(client, migrated_database_url)

    response = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": NOT_CONSENTED}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT
    assert response.json() == {"detail": "The phone number is not permitted for payment requests"}
    assert NOT_CONSENTED not in response.text
    assert attempt_count(migrated_database_url) == 0
    assert fake.requests == []


def test_phone_requests_stay_disabled_until_numbers_are_configured(
    migrated_database_url: str, fake: FakePey
) -> None:
    settings = phone_settings(migrated_database_url, allowed="")
    with start_client(settings, migrated_database_url, fake.provider()) as client:
        sale, operator = open_sale(client, migrated_database_url)
        response = request_phone(
            client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
        )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json() == {"detail": "Phone payment requests are not enabled"}
    assert attempt_count(migrated_database_url) == 0
    assert fake.requests == []


def test_a_lost_provider_answer_keeps_one_verifying_attempt_and_the_retry_does_not_resend(
    migrated_database_url: str,
) -> None:
    lost = FakePey(error=httpx2.ReadTimeout("answer lost"))
    settings = phone_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, lost.provider()) as client:
        sale, operator = open_sale(client, migrated_database_url)
        key = str(uuid.uuid4())
        payload: dict[str, object] = {"method": "phone", "phone_number": CONSENTED}
        first = request_phone(client, operator, sale["id"], payload, key)
        retried = request_phone(client, operator, sale["id"], payload, key)
        other_number = request_phone(
            client, operator, sale["id"], {"method": "phone", "phone_number": OTHER_CONSENTED}, key
        )
        read = client.get(f"/sales/{sale['id']}", headers=operator).json()

    assert first.status_code == HTTPStatus.ACCEPTED
    assert retried.status_code == HTTPStatus.OK
    assert retried.json()["id"] == first.json()["id"]
    assert retried.json()["status"] == "reconciling"
    assert other_number.status_code == HTTPStatus.CONFLICT
    assert len(posted(lost)) == 1
    assert [(item["id"], item["status"], item["next_action"]) for item in read["attempts"]] == [
        (first.json()["id"], "reconciling", "wait_for_verification")
    ]
    assert first.json()["provider_request_id"] is None
    jobs = scalar(migrated_database_url, "SELECT reason || ':' || status FROM reconciliation_jobs")
    assert jobs == "timeout:pending"


@pytest.mark.parametrize(
    ("status", "example", "code"),
    [
        (400, ("400", "invalidPhone"), "INVALID_PARAMETER"),
        (400, ("400", "codiNotEnabled"), "INVALID_STATE"),
        (429, ("429", "default"), "CALL_LIMIT_REACHED"),
    ],
)
def test_a_definitive_rejection_fails_the_phone_request_with_its_code(
    migrated_database_url: str, status: int, example: tuple[str, str], code: str
) -> None:
    rejecting = FakePey(status=status, body=PUSH_FIXTURE["responses"][example[0]][example[1]])
    settings = phone_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, rejecting.provider()) as client:
        sale, operator = open_sale(client, migrated_database_url)
        response = request_phone(
            client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
        )
        read = client.get(f"/sales/{sale['id']}", headers=operator).json()

    assert response.status_code == HTTPStatus.BAD_GATEWAY
    failures = [(item["status"], item["failure_code"]) for item in read["attempts"]]
    assert failures == [("failed", code)]


@pytest.mark.parametrize(
    "answer",
    [
        (500, PUSH_FIXTURE["responses"]["500"]["invokeError"]),
        (503, PUSH_FIXTURE["responses"]["503"]["maintenance"]),
        (200, {"transactionId": "01J5KXYZ1234567890ABCD"}),
        (200, "not json"),
    ],
)
def test_a_server_error_or_an_unusable_answer_keeps_the_request_verifying(
    migrated_database_url: str, answer: tuple[int, object]
) -> None:
    unsure = FakePey(status=answer[0], body=answer[1])
    settings = phone_settings(migrated_database_url)
    with start_client(settings, migrated_database_url, unsure.provider()) as client:
        sale, operator = open_sale(client, migrated_database_url)
        response = request_phone(
            client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
        )

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json()["status"] == "reconciling"
    assert response.json()["provider_request_id"] is None


def test_the_simulated_provider_creates_a_marked_pending_request(
    migrated_database_url: str,
) -> None:
    with start_client(phone_settings(migrated_database_url), migrated_database_url) as client:
        sale, operator = open_sale(client, migrated_database_url)
        response = request_phone(
            client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
        )

    body = response.json()
    assert response.status_code == HTTPStatus.CREATED
    assert (body["status"], body["simulated"], body["next_action"]) == (
        "pending",
        True,
        "wait_for_payment",
    )
    assert body["provider_request_id"].startswith("SIM-")
    assert body["provider_folio"] is not None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5512345678", "5512345678"),
        ("55 1234 5678", "5512345678"),
        ("55-1234-5678", "5512345678"),
        ("+52 55 1234 5678", "5512345678"),
        ("525512345678", "5512345678"),
    ],
)
def test_a_phone_number_is_normalized_to_ten_digits(raw: str, expected: str) -> None:
    assert normalized_phone(raw) == expected


@pytest.mark.parametrize(
    "raw", ["551234567", "+1 555 123 4567", "55 1234 567a", "", FULLWIDTH_DIGITS]
)
def test_a_malformed_phone_number_is_refused(raw: str) -> None:
    with pytest.raises(PhoneNumberError):
        normalized_phone(raw)


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


def test_the_demo_list_only_accepts_ten_digit_numbers() -> None:
    with pytest.raises(ValidationError, match="exactly 10 digits"):
        demo_list_settings("test", "5512345678,551234")


@pytest.mark.parametrize("environment", ["local", "integration", "production"])
def test_phone_requests_cannot_be_enabled_until_their_payments_can_be_verified(
    environment: str,
) -> None:
    with pytest.raises(ValidationError, match="until phone payments can be verified"):
        demo_list_settings(environment, CONSENTED)

    assert demo_list_settings(environment, "").phone_request_numbers == frozenset()


def test_phone_requests_stay_off_the_real_provider_until_verifiable() -> None:
    with pytest.raises(ValidationError, match="until phone payments can be verified"):
        demo_list_settings("test", CONSENTED, provider="pey")


def test_a_list_built_in_code_is_held_to_the_same_ten_digit_rule() -> None:
    assert phone_list(frozenset({CONSENTED})) == frozenset({CONSENTED})
    with pytest.raises(ValueError, match="exactly 10 digits"):
        phone_list(frozenset({"abc"}))


def test_a_phone_request_is_never_queried_through_the_qr_payments_endpoint(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator = open_sale(client, migrated_database_url)
    created = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
    ).json()
    database = Database.from_settings(build_settings(database_url=migrated_database_url))
    try:
        report = reconcile_attempt(
            database, uuid.UUID(created["id"]), fake.provider(), "test", SystemClock()
        )
    finally:
        database.dispose()

    assert report.result is ReconciliationResult.NOT_QUERYABLE
    assert fake.queries() == []


def test_a_phone_request_conflicts_with_an_active_attempt_without_calling_the_provider(
    client: TestClient, migrated_database_url: str, fake: FakePey
) -> None:
    sale, operator = open_sale(client, migrated_database_url)
    first = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED}
    )

    second = request_phone(
        client, operator, sale["id"], {"method": "phone", "phone_number": OTHER_CONSENTED}
    )

    assert first.status_code == HTTPStatus.CREATED
    assert second.status_code == HTTPStatus.CONFLICT
    assert len(posted(fake)) == 1
    assert attempt_count(migrated_database_url) == 1


def test_the_number_is_only_kept_behind_a_keyed_fingerprint(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator = open_sale(client, migrated_database_url)

    request_phone(client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED})

    content = {"sale_id": sale["id"], "method": "phone"}
    keyed = digest_of({**content, "phone": phone_fingerprint(CONSENTED, VALID_SECRET)})
    unkeyed = digest_of({**content, "phone": hashlib.sha256(CONSENTED.encode()).hexdigest()})
    stored = scalar(
        migrated_database_url,
        "SELECT request_digest FROM idempotency_requests WHERE operation = 'create_attempt'",
    )
    unprefixed = hmac.new(VALID_SECRET.encode(), CONSENTED.encode(), hashlib.sha256).hexdigest()
    assert stored == keyed
    assert stored != unkeyed
    assert stored != digest_of({**content, "phone": unprefixed})
    assert (
        scalar(
            migrated_database_url,
            "SELECT count(*) FROM idempotency_requests "
            "WHERE row_to_json(idempotency_requests)::text LIKE :n",
            {"n": f"%{CONSENTED}%"},
        )
        == 0
    )


def test_an_expired_phone_request_blocks_new_attempts_until_payments_can_be_verified(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator = open_sale(client, migrated_database_url)
    request_phone(client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED})
    execute(
        migrated_database_url,
        "UPDATE payment_attempts SET expires_at = now() - interval '1 minute'",
    )

    expired = client.get(f"/sales/{sale['id']}", headers=operator).json()
    batch = run_sales(migrated_database_url, "run-jobs")
    retried = request_phone(client, operator, sale["id"], {"method": "qr"})

    assert [(item["status"], item["next_action"]) for item in expired["attempts"]] == [
        ("expired", "verify_before_retry")
    ]
    assert "exhausted: 1" in batch.stdout
    assert retried.status_code == HTTPStatus.CONFLICT
    assert retried.json() == {
        "detail": "The previous attempt expired; verify it before creating another"
    }


def test_a_withdrawn_phone_request_asks_for_no_action(
    client: TestClient, migrated_database_url: str
) -> None:
    sale, operator = open_sale(client, migrated_database_url)
    request_phone(client, operator, sale["id"], {"method": "phone", "phone_number": CONSENTED})
    execute(migrated_database_url, "UPDATE payment_attempts SET withdrawn_at = now()")

    read = client.get(f"/sales/{sale['id']}", headers=operator).json()

    assert read["attempts"][0]["next_action"] == "none"
