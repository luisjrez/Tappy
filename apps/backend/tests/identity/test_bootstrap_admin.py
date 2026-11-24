import re
from typing import NamedTuple

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tappy.identity.passwords import hash_password, verify_password
from tests.support import run_identity

ADMIN_EMAIL = "admin@tappy.example"
ADMIN_PASSWORD = "correct horse battery staple"


def test_bootstrap_admin_reports_active_admin_without_exposing_password(
    migrated_database_url: str,
) -> None:
    provisioned = run_identity(
        migrated_database_url,
        "bootstrap-admin",
        "--email",
        ADMIN_EMAIL,
        stdin=f"{ADMIN_PASSWORD}\n",
    )
    shown = run_identity(migrated_database_url, "show", "--email", ADMIN_EMAIL)

    assert provisioned.returncode == 0, provisioned.stderr
    reference = re.search(r"reference: ([0-9a-f-]{36})", provisioned.stdout)
    assert reference is not None
    assert "role: admin" in provisioned.stdout
    assert "status: active" in provisioned.stdout
    assert shown.returncode == 0, shown.stderr
    assert f"reference: {reference.group(1)}" in shown.stdout
    assert "role: admin" in shown.stdout
    assert "status: active" in shown.stdout
    for output in (provisioned.stdout, provisioned.stderr, shown.stdout, shown.stderr):
        assert ADMIN_PASSWORD not in output


class StoredIdentity(NamedTuple):
    email: str
    password_hash: str
    role: str
    status: str


def stored_users(database_url: str) -> list[StoredIdentity]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT email, password_hash, role, status FROM identities")
            )
            return [StoredIdentity(*row) for row in rows]
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("", ADMIN_PASSWORD),
        ("not-an-email", ADMIN_PASSWORD),
        (ADMIN_EMAIL, ""),
        (ADMIN_EMAIL, "short-pass"),
        (ADMIN_EMAIL, "x" * 129),
        (ADMIN_EMAIL, "Password1234"),
    ],
)
def test_invalid_bootstrap_input_creates_nothing_and_hides_password(
    migrated_database_url: str, email: str, password: str
) -> None:
    result = run_identity(
        migrated_database_url, "bootstrap-admin", "--email", email, stdin=f"{password}\n"
    )

    assert result.returncode != 0
    assert "Error:" in result.stderr
    assert stored_users(migrated_database_url) == []
    if password:
        assert password not in result.stdout + result.stderr


def test_repeating_bootstrap_keeps_single_identity_and_original_password(
    migrated_database_url: str,
) -> None:
    first = run_identity(
        migrated_database_url,
        "bootstrap-admin",
        "--email",
        ADMIN_EMAIL,
        stdin=f"{ADMIN_PASSWORD}\n",
    )
    original = stored_users(migrated_database_url)

    repeated = run_identity(
        migrated_database_url,
        "bootstrap-admin",
        "--email",
        ADMIN_EMAIL.upper(),
        stdin="a completely different passphrase\n",
    )

    assert first.returncode == 0, first.stderr
    assert repeated.returncode != 0
    assert "already exists" in repeated.stderr
    assert stored_users(migrated_database_url) == original
    assert verify_password(original[0].password_hash, ADMIN_PASSWORD)


def test_bootstrap_never_elevates_an_existing_operator(migrated_database_url: str) -> None:
    engine = create_engine(migrated_database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO identities (id, email, password_hash, role, status) "
                    "VALUES (gen_random_uuid(), :email, :hash, 'operator', 'active')"
                ),
                {"email": ADMIN_EMAIL, "hash": hash_password(ADMIN_PASSWORD)},
            )
    finally:
        engine.dispose()

    result = run_identity(
        migrated_database_url,
        "bootstrap-admin",
        "--email",
        ADMIN_EMAIL,
        stdin=f"{ADMIN_PASSWORD}\n",
    )

    assert result.returncode != 0
    assert [user.role for user in stored_users(migrated_database_url)] == ["operator"]


def test_stored_password_is_an_argon2id_hash(migrated_database_url: str) -> None:
    run_identity(
        migrated_database_url,
        "bootstrap-admin",
        "--email",
        ADMIN_EMAIL,
        stdin=f"{ADMIN_PASSWORD}\n",
    )

    [stored] = stored_users(migrated_database_url)

    assert stored.password_hash.startswith("$argon2id$")
    assert ADMIN_PASSWORD not in stored.password_hash


def test_windows_line_ending_is_not_part_of_the_password(migrated_database_url: str) -> None:
    run_identity(
        migrated_database_url,
        "bootstrap-admin",
        "--email",
        ADMIN_EMAIL,
        stdin=f"{ADMIN_PASSWORD}\r\n",
    )

    [stored] = stored_users(migrated_database_url)

    assert verify_password(stored.password_hash, ADMIN_PASSWORD)


def test_database_rejects_emails_differing_only_by_case(migrated_database_url: str) -> None:
    engine = create_engine(migrated_database_url)
    insert = text(
        "INSERT INTO identities (id, email, password_hash, role, status) "
        "VALUES (gen_random_uuid(), :email, 'hash', 'operator', 'active')"
    )
    try:
        with engine.begin() as connection:
            connection.execute(insert, {"email": "case@tappy.example"})
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(insert, {"email": "CASE@tappy.example"})
    finally:
        engine.dispose()
