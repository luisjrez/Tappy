import hashlib
import hmac
import re

PHONE_DIGITS = 10
VISIBLE_DIGITS = 4
SEPARATORS = re.compile(r"[ .-]")
MEXICAN_PHONE = re.compile(rf"(?:\+?52)?([0-9]{{{PHONE_DIGITS}}})")
PHONE_LIST_ENTRY = re.compile(rf"[0-9]{{{PHONE_DIGITS}}}")


class PhoneNumberError(ValueError):
    def __init__(self) -> None:
        super().__init__(f"The phone number must have {PHONE_DIGITS} digits")


def normalized_phone(raw: str) -> str:
    found = MEXICAN_PHONE.fullmatch(SEPARATORS.sub("", raw))
    if found is None:
        raise PhoneNumberError
    return found.group(1)


def masked_phone(suffix: str) -> str:
    return "*" * (PHONE_DIGITS - VISIBLE_DIGITS) + suffix[-VISIBLE_DIGITS:]


def phone_fingerprint(number: str, key: str) -> str:
    return hmac.new(key.encode(), number.encode(), hashlib.sha256).hexdigest()


def phone_list(raw: object) -> frozenset[str]:
    if isinstance(raw, frozenset):
        return frozenset(str(entry) for entry in raw)
    entries = [entry.strip() for entry in str(raw).split(",") if entry.strip()]
    if not all(PHONE_LIST_ENTRY.fullmatch(entry) for entry in entries):
        raise ValueError(f"Each permitted phone number must have exactly {PHONE_DIGITS} digits")
    return frozenset(entries)
