import json
import subprocess
import sys
from pathlib import Path

from quality.api_diff import Difference, compare

BASELINE_BODY: dict[str, object] = {
    "id": "sale-1",
    "amount_cents": 15000,
    "created_at": "2026-11-20T10:00:00Z",
    "attempts": [{"sale_id": "sale-1", "state": "pending"}],
}
BASELINE: dict[str, object] = {"status": 200, "body": BASELINE_BODY}
NORMALIZED = ("body.id", "body.created_at", "body.attempts[*].sale_id")


def with_body(**changes: object) -> dict[str, object]:
    return {"status": 200, "body": {**BASELINE_BODY, **changes}}


def test_declared_volatile_values_are_normalized_preserving_relations() -> None:
    current = with_body(
        id="sale-9",
        created_at="2026-11-21T08:30:00Z",
        attempts=[{"sale_id": "sale-9", "state": "pending"}],
    )

    assert compare(BASELINE, current, NORMALIZED) == []


def test_broken_reference_is_reported_after_normalization() -> None:
    current = with_body(id="sale-9", attempts=[{"sale_id": "sale-7", "state": "pending"}])

    differences = compare(BASELINE, current, NORMALIZED)

    assert [difference.path for difference in differences] == ["body.attempts[0].sale_id"]


def test_reports_type_presence_and_value_changes() -> None:
    current = {
        "status": 200,
        "body": {
            "id": "sale-1",
            "amount_cents": "15000",
            "attempts": [{"sale_id": "sale-1", "state": "paid"}],
            "currency": "MXN",
        },
    }

    differences = compare(BASELINE, current, NORMALIZED)

    assert differences == [
        Difference("body.amount_cents", "type", "15000", "'15000'"),
        Difference("body.created_at", "removed", "'<normalized:2>'", None),
        Difference("body.attempts[0].state", "value", "'pending'", "'paid'"),
        Difference("body.currency", "added", None, "'MXN'"),
    ]


def test_list_order_is_significant() -> None:
    baseline = {"body": {"items": ["first", "second"]}}
    current = {"body": {"items": ["second", "first"]}}

    differences = compare(baseline, current, ())

    assert [difference.path for difference in differences] == ["body.items[0]", "body.items[1]"]


def test_command_reports_difference_without_touching_baseline(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    baseline_path.write_text(json.dumps(BASELINE))
    current_path.write_text(json.dumps(with_body(amount_cents=15100)))
    original = baseline_path.read_bytes()

    result = subprocess.run(
        [sys.executable, "-m", "quality.api_diff", str(baseline_path), str(current_path)]
        + [f"--normalize={path}" for path in NORMALIZED],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "body.amount_cents" in result.stdout
    assert baseline_path.read_bytes() == original
