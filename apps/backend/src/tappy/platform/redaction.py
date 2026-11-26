import re
from collections.abc import Iterable

REDACTED = "[redacted]"
VISIBLE_DIGITS = 4
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
WEBHOOK_SECRET = re.compile(r"\bwhsec_[A-Za-z0-9+/=]+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ENCODED_SEPARATOR = re.compile(r"%2[0bB]")
ALONE_BEFORE = r"(?:(?<=%20)|(?<=%2[bB])|(?<![\w+-]))"
ALONE_AFTER = r"(?![\w-])"
SPACE = r"(?: |%20)"
SEPARATOR = r"(?:[ -]|%20)"
PLUS = r"(?:\+|%2[bB])"
CLABE = re.compile(
    ALONE_BEFORE + rf"(?:\d{{18}}|\d{{3}}{SPACE}\d{{3}}{SPACE}\d{{11}}{SPACE}\d)" + ALONE_AFTER
)
PHONE_GROUPS = ((10,), (2, 4, 4), (3, 3, 4))
PHONE_DIGITS = "|".join(
    SEPARATOR.join(rf"\d{{{size}}}" for size in sizes) for sizes in PHONE_GROUPS
)
PHONE = re.compile(ALONE_BEFORE + rf"(?:{PLUS}?52{SEPARATOR}?)?(?:{PHONE_DIGITS})" + ALONE_AFTER)


def masked_digits(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", ENCODED_SEPARATOR.sub("", match.group()))
    return "*" * (len(digits) - VISIBLE_DIGITS) + digits[-VISIBLE_DIGITS:]


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    for secret in filter(None, secrets):
        text = text.replace(secret, REDACTED)
    text = BEARER.sub(f"Bearer {REDACTED}", text)
    text = WEBHOOK_SECRET.sub(f"whsec_{REDACTED}", text)
    text = EMAIL.sub("[email]", text)
    text = CLABE.sub(masked_digits, text)
    return PHONE.sub(masked_digits, text)
