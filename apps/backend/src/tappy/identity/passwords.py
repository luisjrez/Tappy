import unicodedata
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from tappy.identity.errors import PasswordPolicyError
from tappy.platform.config import Settings

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


@dataclass(frozen=True)
class PasswordPolicy:
    minimum_length: int = MINIMUM_LENGTH
    maximum_length: int = MAXIMUM_LENGTH

    @classmethod
    def from_settings(cls, settings: Settings) -> PasswordPolicy:
        return cls(settings.password_min_length, settings.password_max_length)

    def check(self, password: str) -> None:
        candidate = normalized(password)
        if len(candidate) < self.minimum_length:
            raise PasswordPolicyError(
                f"Password must have at least {self.minimum_length} characters"
            )
        if len(candidate) > self.maximum_length:
            raise PasswordPolicyError(
                f"Password must have at most {self.maximum_length} characters"
            )
        if candidate.casefold() in COMMON_PASSWORDS:
            raise PasswordPolicyError("Password is too common")

    def hash(self, password: str) -> str:
        self.check(password)
        return hasher.hash(normalized(password))


DEFAULT_POLICY = PasswordPolicy()


def check_policy(password: str, policy: PasswordPolicy = DEFAULT_POLICY) -> None:
    policy.check(password)


def hash_password(password: str, policy: PasswordPolicy = DEFAULT_POLICY) -> str:
    return policy.hash(password)


UNKNOWN_IDENTITY_HASH = hasher.hash("timing equalizer for unknown identities")


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, normalized(password))
    except VerificationError, InvalidHashError:
        return False
