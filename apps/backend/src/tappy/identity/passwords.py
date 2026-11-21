import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from tappy.identity.errors import PasswordPolicyError

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


def normalized(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def check_policy(password: str) -> None:
    candidate = normalized(password)
    if len(candidate) < MINIMUM_LENGTH:
        raise PasswordPolicyError(f"Password must have at least {MINIMUM_LENGTH} characters")
    if len(candidate) > MAXIMUM_LENGTH:
        raise PasswordPolicyError(f"Password must have at most {MAXIMUM_LENGTH} characters")
    if candidate.casefold() in COMMON_PASSWORDS:
        raise PasswordPolicyError("Password is too common")


def hash_password(password: str) -> str:
    check_policy(password)
    return hasher.hash(normalized(password))


UNKNOWN_IDENTITY_HASH = hasher.hash("timing equalizer for unknown identities")


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, normalized(password))
    except VerificationError, InvalidHashError:
        return False
