import re

VISIBLE_DIGITS = 4
SEPARATORS = re.compile(r"[ .-]")
MEXICAN_PHONE = re.compile(r"(?:\+?52)?([0-9]{10})")
PHONE_LIST_ENTRY = re.compile(r"[0-9]{10}")


class PhoneNumberError(ValueError):
    def __init__(self) -> None:
        super().__init__("The phone number must have 10 digits")


def normalized_phone(raw: str) -> str:
    found = MEXICAN_PHONE.fullmatch(SEPARATORS.sub("", raw))
    if found is None:
        raise PhoneNumberError
    return found.group(1)


def masked_phone(suffix: str) -> str:
    return "*" * 6 + suffix[-VISIBLE_DIGITS:]


def phone_list(raw: str) -> frozenset[str]:
    entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
    if not all(PHONE_LIST_ENTRY.fullmatch(entry) for entry in entries):
        raise ValueError("Each permitted phone number must have exactly 10 digits")
    return frozenset(entries)
