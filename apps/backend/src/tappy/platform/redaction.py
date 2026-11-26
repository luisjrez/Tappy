import re
from collections.abc import Iterable

REDACTED = "[redacted]"
VISIBLE_DIGITS = 4
BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
WEBHOOK_SECRET = re.compile(r"\bwhsec_[A-Za-z0-9+/=]+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALONE_BEFORE = r"(?<![\w+-])"
ALONE_AFTER = r"(?![\w-])"
CLABE = re.compile(ALONE_BEFORE + r"(?:\d{18}|\d{3} \d{3} \d{11} \d)" + ALONE_AFTER)
PHONE = re.compile(
    ALONE_BEFORE
    + r"(?:\+?52[ -]?)?(?:\d{10}|\d{2}[ -]\d{4}[ -]\d{4}|\d{3}[ -]\d{3}[ -]\d{4})"
    + ALONE_AFTER
)


def masked_digits(match: re.Match[str]) -> str:
    digits = re.sub(r"\D", "", match.group())
    return "*" * (len(digits) - VISIBLE_DIGITS) + digits[-VISIBLE_DIGITS:]


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    for secret in filter(None, secrets):
        text = text.replace(secret, REDACTED)
    text = BEARER.sub(f"Bearer {REDACTED}", text)
    text = WEBHOOK_SECRET.sub(f"whsec_{REDACTED}", text)
    text = EMAIL.sub("[email]", text)
    text = CLABE.sub(masked_digits, text)
    return PHONE.sub(masked_digits, text)
