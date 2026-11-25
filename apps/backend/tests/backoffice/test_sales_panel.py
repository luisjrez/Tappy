import json
import re
import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

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
ROW = re.compile(r'<tr data-sale="([0-9a-f-]+)"')
PRICE = 30000
FORM_ACTION = re.compile(r'<form[^>]*action="([^"]+)"', re.DOTALL)
NEXT = re.compile(r'href="([^"]*cursor=[^"]+)"')


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    for email, role in ((ADMIN, Role.ADMIN), (OPERATOR_A, Role.OPERATOR)):
        create_identity(migrated_database_url, email, PASSWORD, role=role)
    app = create_app(settings_for(migrated_database_url), qr_provider=FakePey().provider())
    with TestClient(app, base_url="https://testserver") as started:
        yield started


def sign_in(client: TestClient, email: str = ADMIN) -> None:
    match = CSRF_FIELD.search(client.get("/admin/login").text)
    assert match is not None
    client.post(
        "/admin/login",
        data={"username": email, "password": PASSWORD, "csrftoken": match.group(1)},
    )


def paid_sale(client: TestClient, database_url: str, amount: int = 30010) -> dict[str, Any]:
    merchant = ready_merchant(client, database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    sale: dict[str, Any] = create_sale(client, operator_a, merchant, amount_cents=amount).json()
    attempt = client.post(
        f"/sales/{sale['id']}/attempts",
        json={"method": "qr"},
        headers={**operator_a, IDEMPOTENCY_HEADER: str(uuid.uuid4())},
    ).json()
    event = {
        "type": "codi.qr.payment_received",
        "amount": amount / 100,
        "bankAccountId": RECEIVER_A["provider_account_id"],
        "codiQrId": attempt["provider_request_id"],
        "datePaid": 1795000000,
        "transactionId": "TX-PANEL-0001",
        "metadata": {"tappy_attempt_id": attempt["id"]},
    }
    deliver(client, json.dumps(event).encode(), Delivery(message_id="msg_panel"))
    return sale


def test_the_admin_sees_sales_with_attempts_transfers_and_amounts(
    client: TestClient, migrated_database_url: str
) -> None:
    sale = paid_sale(client, migrated_database_url)
    sign_in(client)

    listing = client.get("/admin/sales")
    detail = client.get(f"/admin/sales/{sale['id']}")

    assert listing.status_code == HTTPStatus.OK
    assert ROW.findall(listing.text) == [sale["id"]]
    assert sale["reference"] in listing.text
    assert "300.10" in listing.text
    assert "paid" in listing.text
    assert detail.status_code == HTTPStatus.OK
    for expected in (sale["reference"], "300.10", "TX-PANEL-0001", "paid", sale["masked_account"]):
        assert expected in detail.text
    assert str(RECEIVER_A["clabe"]) not in detail.text


def test_operators_cannot_open_the_sales_panel(
    client: TestClient, migrated_database_url: str
) -> None:
    sale = paid_sale(client, migrated_database_url)
    sign_in(client, OPERATOR_A)

    listing = client.get("/admin/sales", follow_redirects=False)
    detail = client.get(f"/admin/sales/{sale['id']}", follow_redirects=False)

    assert listing.status_code in {
        HTTPStatus.SEE_OTHER,
        HTTPStatus.FOUND,
        HTTPStatus.TEMPORARY_REDIRECT,
    }
    assert detail.status_code in {
        HTTPStatus.SEE_OTHER,
        HTTPStatus.FOUND,
        HTTPStatus.TEMPORARY_REDIRECT,
    }
    assert sale["reference"] not in listing.text + detail.text


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_panel_offers_no_way_to_change_money_or_force_a_reception(
    client: TestClient, migrated_database_url: str, method: str
) -> None:
    merchant = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    sale = create_sale(client, bearer(client, OPERATOR_A), merchant, amount_cents=PRICE).json()
    sign_in(client)
    match = CSRF_FIELD.search(client.get("/admin/merchants").text)
    assert match is not None
    forged = {"status": "paid", "amount_cents": "1", "csrftoken": match.group(1)}

    responses = [
        client.request(method.upper(), path, data=forged)
        for path in (
            f"/admin/sales/{sale['id']}",
            f"/admin/sales/{sale['id']}/receive",
            f"/admin/sales/{sale['id']}/delete",
            "/admin/sales",
        )
    ]

    assert {response.status_code for response in responses} <= {
        HTTPStatus.METHOD_NOT_ALLOWED,
        HTTPStatus.NOT_FOUND,
    }
    assert scalar(migrated_database_url, "SELECT status FROM sales") == "open"
    assert scalar(migrated_database_url, "SELECT amount_cents FROM sales") == PRICE
    assert scalar(migrated_database_url, "SELECT count(*) FROM transactions") == 0
    page = client.get(f"/admin/sales/{sale['id']}").text
    assert set(FORM_ACTION.findall(page)) == {"https://testserver/admin/logout"}


@pytest.mark.parametrize(
    "query",
    ["status=cancelled", "limit=0", "limit=51", "cursor=manipulated", "merchant_id=not-a-uuid"],
)
def test_malformed_panel_filters_are_client_errors(
    client: TestClient, migrated_database_url: str, query: str
) -> None:
    paid_sale(client, migrated_database_url)
    sign_in(client)

    response = client.get(f"/admin/sales?{query}")

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_an_unknown_sale_or_merchant_is_not_found_in_the_panel(
    client: TestClient, migrated_database_url: str
) -> None:
    paid_sale(client, migrated_database_url)
    sign_in(client)

    unknown_sale = client.get(f"/admin/sales/{uuid.uuid4()}")
    unknown_merchant = client.get(f"/admin/sales?merchant_id={uuid.uuid4()}")

    assert unknown_sale.status_code == HTTPStatus.NOT_FOUND
    assert unknown_merchant.status_code == HTTPStatus.NOT_FOUND


def test_panel_pages_recover_every_sale_without_hidden_truncation(
    client: TestClient, migrated_database_url: str
) -> None:
    merchant = ready_merchant(client, migrated_database_url, "Tienda Demo A", OPERATOR_A)
    operator_a = bearer(client, OPERATOR_A)
    created = [
        create_sale(client, operator_a, merchant, amount_cents=1000 + index).json()["id"]
        for index in range(5)
    ]
    sign_in(client)

    seen: list[str] = []
    url: str | None = "/admin/sales?limit=2&status=open"
    while url is not None:
        page = client.get(url.replace("&amp;", "&")).text
        seen.extend(ROW.findall(page))
        found = NEXT.search(page)
        url = found.group(1) if found else None

    assert sorted(seen) == sorted(created)
    assert len(seen) == len(set(seen))
