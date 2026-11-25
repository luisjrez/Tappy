import json
import re
import uuid
from collections.abc import Iterator
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from tappy.identity.models import Role
from tappy.main import create_app
from tests.payments.pey_support import FakePey
from tests.payments.webhook_support import Delivery, deliver, settings_for
from tests.sales.support import (
    ADMIN,
    IDEMPOTENCY_HEADER,
    OPERATOR_A,
    PASSWORD,
    RECEIVER_A,
    bearer,
    create_sale,
    ready_merchant,
)
from tests.support import create_identity, scalar

CSRF_FIELD = re.compile(r'name="csrftoken" value="([^"]+)"')
NOTE = "Called the merchant; waiting for the bank statement"


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    for email, role in ((ADMIN, Role.ADMIN), (OPERATOR_A, Role.OPERATOR)):
        create_identity(migrated_database_url, email, PASSWORD, role=role)
    app = create_app(settings_for(migrated_database_url), qr_provider=FakePey().provider())
    with TestClient(app, base_url="https://testserver") as started:
        yield started


def csrf(client: TestClient, path: str) -> str:
    match = CSRF_FIELD.search(client.get(path).text)
    assert match is not None
    return match.group(1)


def sign_in(client: TestClient, email: str = ADMIN) -> None:
    client.post(
        "/admin/login",
        data={"username": email, "password": PASSWORD, "csrftoken": csrf(client, "/admin/login")},
    )


def short_payment(client: TestClient, database_url: str) -> str:
    merchant = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale = create_sale(client, operator_a, merchant, amount_cents=30000).json()
    attempt = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()
    event = {
        "type": "codi.qr.payment_received",
        "amount": 250.0,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": 1795000000,
        "transactionId": "TX-PANEL-SHORT",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    deliver(client, json.dumps(event).encode(), Delivery(message_id="msg_panel_short"))
    return str(scalar(database_url, "SELECT id FROM payment_exceptions"))


def money(database_url: str) -> tuple[object, ...]:
    return (
        scalar(database_url, "SELECT status FROM sales"),
        scalar(database_url, "SELECT sum(amount_cents) FROM transactions"),
        scalar(database_url, "SELECT count(*) FROM payment_exceptions WHERE resolved_at IS NULL"),
    )


def test_the_admin_notes_and_requests_reconciliation_from_the_panel(
    client: TestClient, migrated_database_url: str
) -> None:
    exception_id = short_payment(client, migrated_database_url)
    before = money(migrated_database_url)
    sign_in(client)
    page = f"/admin/exceptions/{exception_id}"

    listed = client.get("/admin/exceptions")
    noted = client.post(
        f"{page}/notes",
        data={"text": NOTE, "csrftoken": csrf(client, page)},
        follow_redirects=False,
    )
    requested = client.post(
        f"{page}/reconciliation", data={"csrftoken": csrf(client, page)}, follow_redirects=False
    )
    detail = client.get(page).text

    assert exception_id in listed.text
    assert "amount_mismatch" in listed.text
    assert noted.status_code == HTTPStatus.SEE_OTHER
    assert requested.status_code == HTTPStatus.SEE_OTHER
    assert NOTE in detail
    assert "Reconciliation requested (created)" in detail
    assert ADMIN in detail
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 1
    assert money(migrated_database_url) == before


def test_a_second_request_from_the_panel_keeps_one_job(
    client: TestClient, migrated_database_url: str
) -> None:
    exception_id = short_payment(client, migrated_database_url)
    sign_in(client)
    page = f"/admin/exceptions/{exception_id}"

    for _ in range(2):
        client.post(f"{page}/reconciliation", data={"csrftoken": csrf(client, page)})
    detail = client.get(page).text

    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 1
    assert "Reconciliation requested (already_pending)" in detail


def test_without_a_valid_csrf_token_nothing_is_written(
    client: TestClient, migrated_database_url: str
) -> None:
    exception_id = short_payment(client, migrated_database_url)
    before = money(migrated_database_url)
    sign_in(client)
    page = f"/admin/exceptions/{exception_id}"

    forged_note = client.post(f"{page}/notes", data={"text": NOTE, "csrftoken": "forged"})
    missing = client.post(f"{page}/reconciliation", data={})

    assert forged_note.status_code == HTTPStatus.FORBIDDEN
    assert missing.status_code == HTTPStatus.FORBIDDEN
    assert scalar(migrated_database_url, "SELECT count(*) FROM exception_notes") == 0
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 0
    assert money(migrated_database_url) == before


def test_operators_cannot_review_incidents_in_the_panel(
    client: TestClient, migrated_database_url: str
) -> None:
    exception_id = short_payment(client, migrated_database_url)
    sign_in(client, OPERATOR_A)

    page = client.get(f"/admin/exceptions/{exception_id}", follow_redirects=False)
    token = csrf(client, "/admin/login")
    posts = [
        client.post(
            f"/admin/exceptions/{exception_id}/{action}",
            data={"text": NOTE, "csrftoken": token},
            follow_redirects=False,
        )
        for action in ("notes", "reconciliation")
    ]

    assert page.status_code == HTTPStatus.SEE_OTHER
    assert {post.status_code for post in posts} <= {HTTPStatus.SEE_OTHER, HTTPStatus.FORBIDDEN}
    assert scalar(migrated_database_url, "SELECT count(*) FROM exception_notes") == 0
    assert scalar(migrated_database_url, "SELECT count(*) FROM reconciliation_jobs") == 0


def test_an_empty_note_is_refused_with_a_message(
    client: TestClient, migrated_database_url: str
) -> None:
    exception_id = short_payment(client, migrated_database_url)
    sign_in(client)
    page = f"/admin/exceptions/{exception_id}"

    detail = client.post(
        f"{page}/notes", data={"text": "   ", "csrftoken": csrf(client, page)}
    ).text

    assert "A note needs between 1 and 1000 characters" in detail
    assert scalar(migrated_database_url, "SELECT count(*) FROM exception_notes") == 0
