from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MINIMUM_LENGTH = 12
MAXIMUM_LENGTH = 128
COMMON_PASSWORDS = frozenset(
    {
        "123456789012",
        "1234567890123",
        "12345678901234",
        "password1234",
        "password12345",
        "passwordpassword",
        "qwertyuiopas",
        "qwertyuiop123",
        "iloveyou1234",
        "contraseña123",
        "contrasena123",
        "contraseña1234",
        "administrador",
        "administrator",
        "tappytappy12",
        "111111111111",
        "000000000000",
        "aaaaaaaaaaaa",
        "abcdefghijkl",
        "abc123456789",
    }
)

hasher = PasswordHasher()


class PasswordPolicyError(ValueError):
    pass


def check_policy(password: str) -> None:
    if len(password) < MINIMUM_LENGTH:
        raise PasswordPolicyError(f"Password must have at least {MINIMUM_LENGTH} characters")
    if len(password) > MAXIMUM_LENGTH:
        raise PasswordPolicyError(f"Password must have at most {MAXIMUM_LENGTH} characters")
    if password.casefold() in COMMON_PASSWORDS:
        raise PasswordPolicyError("Password is too common")


def hash_password(password: str) -> str:
    check_policy(password)
    return hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except VerificationError, InvalidHashError:
        return False
