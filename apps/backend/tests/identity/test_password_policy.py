import pytest

from tappy.identity.passwords import (
    PasswordPolicyError,
    check_policy,
    hash_password,
    verify_password,
)


@pytest.mark.parametrize("password", ["a" * 11 + "b", "long passphrase " * 8])
def test_accepts_passwords_at_the_length_limits(password: str) -> None:
    check_policy(password)


@pytest.mark.parametrize("password", ["eleven-char", "x" * 129, "ADMINISTRATOR", "Contraseña123"])
def test_rejects_short_long_and_common_passwords(password: str) -> None:
    with pytest.raises(PasswordPolicyError):
        check_policy(password)


def test_hash_verifies_only_the_original_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "correct horse battery stapler")
    assert not verify_password("not-a-hash", "correct horse battery staple")
