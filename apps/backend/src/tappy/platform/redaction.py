import re
from collections.abc import Iterable

REDACTED = "[redacted]"
VISIBLE_DIGITS = 4
MIN_SECRET_LENGTH = 8
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
WEBHOOK_SECRET = re.compile(r"\bwhsec_[A-Za-z0-9+/=]+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ENCODED_SEPARATOR = re.compile(r"%2[0bB]")
ALONE_BEFORE = r"(?:(?<=%20)|(?<=%2[bB])|(?<![\w+-]))"
ALONE_AFTER = r"(?![\w-])"
SPACE = r"(?: |%20)"
SEPARATOR = r"(?:[ .-]|%20)"
PLUS = r"(?:\+|%2[bB])"


def grouped(sizes: tuple[int, ...], separator: str) -> str:
    return separator.join(rf"\d{{{size}}}" for size in sizes)


def bracketed(sizes: tuple[int, ...]) -> str:
    first, *rest = sizes
    return rf"\({grouped((first,), '')}\){SEPARATOR}?" + grouped(tuple(rest), SEPARATOR)


CLABE_GROUPS = ((18,), (3, 3, 11, 1), (4, 4, 4, 4, 2))
CLABE_DIGITS = "|".join(grouped(sizes, SPACE) for sizes in CLABE_GROUPS)
CLABE = re.compile(ALONE_BEFORE + rf"(?:{CLABE_DIGITS})" + ALONE_AFTER)
PHONE_GROUPS = ((2, 4, 4), (3, 3, 4))
PHONE_DIGITS = "|".join(
    [
        grouped((10,), SEPARATOR),
        *(grouped(sizes, SEPARATOR) for sizes in PHONE_GROUPS),
        *(bracketed(sizes) for sizes in PHONE_GROUPS),
    ]
)
PHONE_PREFIX = rf"(?:{PLUS}?52{SEPARATOR}?(?:1{SEPARATOR}?)?)?"
PHONE = re.compile(ALONE_BEFORE + PHONE_PREFIX + rf"(?:{PHONE_DIGITS})" + ALONE_AFTER)


def masked_digits(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", ENCODED_SEPARATOR.sub("", match.group()))
    return "*" * (len(digits) - VISIBLE_DIGITS) + digits[-VISIBLE_DIGITS:]


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    distinct = {secret for secret in secrets if len(secret) >= MIN_SECRET_LENGTH}
    for secret in sorted(distinct, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    text = BEARER.sub(f"Bearer {REDACTED}", text)
    text = WEBHOOK_SECRET.sub(f"whsec_{REDACTED}", text)
    text = EMAIL.sub("[email]", text)
    text = CLABE.sub(masked_digits, text)
    return PHONE.sub(masked_digits, text)
