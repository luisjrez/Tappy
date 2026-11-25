import hashlib
import json
import time
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tappy.main import create_app
from tappy.platform.config import Settings
from tests.payments.webhook_support import (
    EVENT,
    MAX_BODY,
    OTHER_SECRET,
    SECRET,
    Delivery,
    deliver,
    encoded,
    settings_for,
    signature,
)
from tests.support import UNREACHABLE_DATABASE_URL, build_settings, scalar


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(settings_for(migrated_database_url))) as client:
        yield client


def event_count(database_url: str) -> object:
    return scalar(database_url, "SELECT count(*) FROM webhook_events")


def test_valid_event_is_stored_durably_before_success(
    client: TestClient, migrated_database_url: str
) -> None:
    body = encoded()

    response = deliver(client, body)

    assert response.status_code == HTTPStatus.NO_CONTENT
    stored = scalar(
        migrated_database_url,
        "SELECT provider || '|' || provider_event_id || '|' || event_type || '|' || status "
        "|| '|' || payload_digest FROM webhook_events",
    )
    assert stored == (
        f"pey|msg_synthetic_0001|codi.qr.payment_received|review|{hashlib.sha256(body).hexdigest()}"
    )
    assert scalar(migrated_database_url, "SELECT payload FROM webhook_events") == body


def test_repeated_delivery_is_acknowledged_without_a_second_record(
    client: TestClient, migrated_database_url: str
) -> None:
    body = encoded()

    first = deliver(client, body)
    repeated = deliver(client, body)

    assert first.status_code == HTTPStatus.NO_CONTENT
    assert repeated.status_code == HTTPStatus.NO_CONTENT
    assert event_count(migrated_database_url) == 1


def test_signatures_from_a_rotated_header_list_are_accepted(
    client: TestClient, migrated_database_url: str
) -> None:
    body = encoded()
    stamp = str(int(time.time()))
    headers = {
        "webhook-id": "msg_rotated",
        "webhook-timestamp": stamp,
        "webhook-signature": " ".join(
            [
                signature(OTHER_SECRET, "msg_rotated", stamp, body),
                signature(SECRET, "msg_rotated", stamp, body),
            ]
        ),
    }

    response = client.post("/webhooks/pey", content=body, headers=headers)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert event_count(migrated_database_url) == 1


@pytest.mark.parametrize(
    "variant",
    ["altered_body", "wrong_secret", "old_timestamp", "future_timestamp"],
)
def test_untrusted_deliveries_are_rejected_without_effects(
    client: TestClient, migrated_database_url: str, variant: str
) -> None:
    body = encoded()
    now = int(time.time())
    deliveries = {
        "altered_body": lambda: deliver(
            client, body.replace(b"300.1", b"999.9"), Delivery(signed_body=body)
        ),
        "wrong_secret": lambda: deliver(client, body, Delivery(secret=OTHER_SECRET)),
        "old_timestamp": lambda: deliver(client, body, Delivery(timestamp=now - 600)),
        "future_timestamp": lambda: deliver(client, body, Delivery(timestamp=now + 600)),
    }

    response = deliveries[variant]()

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"detail": "Invalid webhook signature"}
    assert event_count(migrated_database_url) == 0


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"webhook-id": "msg_x", "webhook-timestamp": "not-a-number", "webhook-signature": "v1,x"},
        {"webhook-id": "msg_x", "webhook-timestamp": "1", "webhook-signature": "garbage"},
    ],
)
def test_missing_or_malformed_headers_are_rejected(
    client: TestClient, migrated_database_url: str, headers: dict[str, str]
) -> None:
    response = client.post("/webhooks/pey", content=encoded(), headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert event_count(migrated_database_url) == 0


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[]", encoded({"amount": 1}), encoded({"type": ""}), encoded({"type": 7})],
)
def test_signed_events_with_an_invalid_schema_are_rejected(
    client: TestClient, migrated_database_url: str, body: bytes
) -> None:
    response = deliver(client, body)

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert event_count(migrated_database_url) == 0


def test_oversized_bodies_are_rejected_before_verification(
    client: TestClient, migrated_database_url: str
) -> None:
    body = encoded({**EVENT, "padding": "x" * MAX_BODY})

    response = deliver(client, body)

    assert response.status_code == HTTPStatus.CONTENT_TOO_LARGE
    assert event_count(migrated_database_url) == 0


def test_reception_without_a_configured_secret_is_unavailable(
    migrated_database_url: str,
) -> None:
    with TestClient(create_app(build_settings(database_url=migrated_database_url))) as client:
        response = deliver(client, encoded())

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert event_count(migrated_database_url) == 0


def test_unavailable_storage_answers_a_temporary_error_and_a_retry_keeps_the_event(
    migrated_database_url: str,
) -> None:
    body = encoded()
    with TestClient(create_app(settings_for(UNREACHABLE_DATABASE_URL))) as unavailable:
        failed = deliver(unavailable, body)
    with TestClient(create_app(settings_for(migrated_database_url))) as available:
        retried = deliver(available, body)

    assert failed.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert failed.json() == {"detail": "Webhook storage is temporarily unavailable"}
    assert retried.status_code == HTTPStatus.NO_CONTENT
    assert event_count(migrated_database_url) == 1


def test_secret_is_never_echoed(client: TestClient) -> None:
    response = deliver(client, encoded(), Delivery(secret=OTHER_SECRET))

    assert SECRET not in response.text
    assert OTHER_SECRET not in response.text


def test_webhook_secret_setting_is_validated_like_any_configuration() -> None:
    base = build_settings().model_dump()

    configured = Settings.model_validate({**base, "pey_webhook_secret": SECRET})
    assert configured.pey_webhook_secret is not None
    assert configured.pey_webhook_secret.get_secret_value() == SECRET
    assert SECRET not in repr(configured)
    for invalid in ("not-a-secret", "whsec_short", "whsec_" + "!" * 40):
        with pytest.raises(ValueError, match="pey_webhook_secret"):
            Settings.model_validate({**base, "pey_webhook_secret": invalid})


@pytest.mark.parametrize("stamp", ["9" * 400, "9" * 5000, "1" + "0" * 13])
def test_absurd_timestamps_are_rejected_as_invalid(
    client: TestClient, migrated_database_url: str, stamp: str
) -> None:
    body = encoded()
    headers = {
        "webhook-id": "msg_absurd",
        "webhook-timestamp": stamp,
        "webhook-signature": signature(SECRET, "msg_absurd", stamp, body),
    }

    response = client.post("/webhooks/pey", content=body, headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert event_count(migrated_database_url) == 0


def test_overlong_event_ids_are_rejected_as_invalid(
    client: TestClient, migrated_database_url: str
) -> None:
    response = deliver(client, encoded(), Delivery(message_id="m" * 256))

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert event_count(migrated_database_url) == 0


@pytest.mark.parametrize("secret", ["whsec_" + "A" * 25, "whsec_" + "A" * 26, "whsec_QUJD"])
def test_secrets_that_do_not_decode_to_a_usable_key_are_refused(secret: str) -> None:
    with pytest.raises(ValueError, match="pey_webhook_secret"):
        Settings.model_validate({**build_settings().model_dump(), "pey_webhook_secret": secret})


def test_the_official_pey_event_shape_is_accepted(
    client: TestClient, migrated_database_url: str
) -> None:
    official = json.loads(
        (Path(__file__).parents[1] / "fixtures" / "pey" / "webhook-codi-qr.json").read_text()
    )["example"]

    response = deliver(client, encoded(official), Delivery(message_id="msg_official"))

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert (
        scalar(migrated_database_url, "SELECT event_type FROM webhook_events")
        == "codi.qr.payment_received"
    )
