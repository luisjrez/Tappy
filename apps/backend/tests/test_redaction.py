import pytest

from tappy.platform.redaction import redact


@pytest.mark.parametrize(
    ("raw", "redacted"),
    [
        ("clabe 002180700123456789", "clabe **************6789"),
        ("clabe 002 180 70012345678 9.", "clabe **************6789."),
        ("phone 5512345678", "phone ******5678"),
        ("phone +525512345678", "phone ********5678"),
        ("phone +52 55 1234 5678", "phone ********5678"),
        ("phone 52-551-234-5678", "phone ********5678"),
        ("phone (55 1234 5678)", "phone (******5678)"),
        ("GET /health?phone=%2B525512345678 HTTP", "GET /health?phone=********5678 HTTP"),
        ("?phone=%2b52%2055%201234%205678&x", "?phone=********5678&x"),
        ("?clabe=002%20180%2070012345678%209&x", "?clabe=**************6789&x"),
        ("?q=tel%205512345678&x", "?q=tel%20******5678&x"),
        ("Authorization: Bearer abc.DEF-123_xyz", "Authorization: Bearer [redacted]"),
        ("secret whsec_c2VjcmV0LXZhbHVl", "secret whsec_[redacted]"),
        ("payer pagador.sintetico@example.com", "payer [email]"),
    ],
)
def test_sensitive_values_are_masked(raw: str, redacted: str) -> None:
    assert redact(raw) == redacted


@pytest.mark.parametrize(
    "kept",
    [
        "attempt 0a1b2c3d-8000-4abc-8000-a123456789bc",
        "job 550e8400-e29b-41d4-a716-446655440000 for sale 5XFJZZS8CT",
        "qr SIM-1234567890AB and pey 01M3QR8H0RH0XBCKYYD242YXNV",
        "qr SIM-1234567890 and order A1234567890",
        "amount_cents 30000 paid at 2026-11-25T16:41:09+00:00",
        "digest 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        "masked account **************6782",
    ],
)
def test_identifiers_amounts_and_dates_are_kept(kept: str) -> None:
    assert redact(kept) == kept


def test_configured_secrets_are_replaced_wherever_they_appear() -> None:
    assert redact("url user:pw-123@host and pw-123", ["pw-123", ""]) == (
        "url user:[redacted]@host and [redacted]"
    )
