import subprocess
import sys
from pathlib import Path

import pytest

from quality.evidence import evaluate, load_manifest, read_junit

FULL_COMPLETENESS = 100
JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
<testcase classname="tests.test_sample" name="test_ok"/>
<testcase classname="tests.test_sample" name="test_other_ok"/>
<testcase classname="tests.test_sample" name="test_param[first]"/>
<testcase classname="tests.test_sample" name="test_param[second]"/>
<testcase classname="tests.test_sample" name="test_broken"><failure message="boom"/></testcase>
<testcase classname="tests.test_sample" name="test_skipped"><skipped message="later"/></testcase>
</testsuite></testsuites>
"""


def criterion(identifier: str, tests: str, *, mandatory: bool = True) -> str:
    return f"""
[[criteria]]
id = "{identifier}"
mandatory = {str(mandatory).lower()}

[[criteria.cases]]
id = "{identifier.replace("AC", "TC")}"
mode = "automated"
tests = [{tests}]
"""


def manifest(*criteria: str, vc01: str = "PASS", pending_findings: int = 0) -> str:
    header = f"""ticket = "B99"

[vc01]
status = "{vc01}"

[review]
pending_findings = {pending_findings}
"""
    return header + "".join(criteria)


def write(tmp_path: Path, content: str) -> tuple[Path, Path]:
    manifest_path = tmp_path / "B99.toml"
    manifest_path.write_text(content)
    junit_path = tmp_path / "junit.xml"
    junit_path.write_text(JUNIT)
    return manifest_path, junit_path


def report_for(tmp_path: Path, content: str) -> tuple[bool, str, float | None]:
    manifest_path, junit_path = write(tmp_path, content)
    report = evaluate(load_manifest(manifest_path), read_junit(junit_path))
    return report.approved, report.render(), report.completeness


def test_all_mandatory_criteria_passing_is_approved(tmp_path: Path) -> None:
    approved, rendered, completeness = report_for(
        tmp_path,
        manifest(
            criterion("B99-AC01", '"tests/test_sample.py::test_ok"'),
            criterion("B99-AC02", '"tests/test_sample.py::test_param"'),
            criterion("B99-AC03", '"tests/test_sample.py::test_other_ok"'),
        ),
    )

    assert approved
    assert completeness == FULL_COMPLETENESS
    assert "B99-AC02 | PASS" in rendered


def passing(count: int, *, prefix: str = "B99-AC") -> list[str]:
    return [
        criterion(f"{prefix}{index:02d}", '"tests/test_sample.py::test_ok"')
        for index in range(1, count + 1)
    ]


@pytest.mark.parametrize(
    ("failing_test", "expected_status"),
    [
        ('"tests/test_sample.py::test_broken"', "FAIL"),
        ('"tests/test_sample.py::test_skipped"', "FAIL"),
        ('"tests/test_sample.py::test_missing"', "NOT_RUN"),
        ("", "NOT_RUN"),
    ],
)
def test_one_unmet_criterion_of_three_blocks_approval(
    tmp_path: Path, failing_test: str, expected_status: str
) -> None:
    approved, rendered, completeness = report_for(
        tmp_path, manifest(*passing(2), criterion("B99-AC03", failing_test))
    )

    assert not approved
    assert completeness == pytest.approx(66.6667, abs=0.001)
    assert f"B99-AC03 | {expected_status}" in rendered


def test_completeness_is_not_rounded_up(tmp_path: Path) -> None:
    content = manifest(
        *passing(32), criterion("B99-AC33", '"tests/test_sample.py::test_broken"', mandatory=False)
    )

    approved, _, completeness = report_for(tmp_path, content)

    assert completeness == pytest.approx(96.9697, abs=0.001)
    assert not approved


def test_agreed_optional_criterion_may_fail_within_margin(tmp_path: Path) -> None:
    content = manifest(
        *passing(33), criterion("B99-AC34", '"tests/test_sample.py::test_broken"', mandatory=False)
    )

    approved, _, completeness = report_for(tmp_path, content)

    assert completeness == pytest.approx(97.0588, abs=0.001)
    assert approved


def test_failing_mandatory_criterion_blocks_even_above_threshold(tmp_path: Path) -> None:
    content = manifest(*passing(33), criterion("B99-AC34", '"tests/test_sample.py::test_broken"'))

    approved, rendered, _ = report_for(tmp_path, content)

    assert not approved
    assert "B99-AC34" in rendered


@pytest.mark.parametrize(
    ("vc01", "pending_findings"), [("NOT_RUN", 0), ("FAIL", 0), ("BLOCKED", 0), ("PASS", 1)]
)
def test_process_conditions_block_full_completeness(
    tmp_path: Path, vc01: str, pending_findings: int
) -> None:
    approved, _, completeness = report_for(
        tmp_path, manifest(*passing(3), vc01=vc01, pending_findings=pending_findings)
    )

    assert completeness == FULL_COMPLETENESS
    assert not approved


def test_manifest_without_applicable_criteria_is_invalid(tmp_path: Path) -> None:
    approved, rendered, completeness = report_for(tmp_path, manifest())

    assert completeness is None
    assert not approved
    assert "sin criterios aplicables" in rendered


def manual_criterion(identifier: str, result: str, evidence: str) -> str:
    return f"""
[[criteria]]
id = "{identifier}"
mandatory = true

[[criteria.cases]]
id = "{identifier.replace("AC", "TC")}"
mode = "external"
result = "{result}"
evidence = "{evidence}"
"""


@pytest.mark.parametrize(
    ("result", "evidence", "expected"),
    [
        ("PASS", "docs/evidence/B99.md#entrega", "PASS"),
        ("PASS", "", "NOT_RUN"),
        ("BLOCKED", "sin acceso al proveedor", "BLOCKED"),
    ],
)
def test_external_case_needs_recorded_result_and_evidence(
    tmp_path: Path, result: str, evidence: str, expected: str
) -> None:
    approved, rendered, _ = report_for(
        tmp_path, manifest(*passing(2), manual_criterion("B99-AC03", result, evidence))
    )

    assert f"B99-AC03 | {expected}" in rendered
    assert approved is (expected == "PASS")


def test_justified_non_applicable_criterion_leaves_denominator(tmp_path: Path) -> None:
    excluded = """
[[criteria]]
id = "B99-AC03"
mandatory = true
applicable = false
justification = "Acordado antes de ejecutar: superficie inexistente en esta etapa"
"""

    approved, rendered, completeness = report_for(tmp_path, manifest(*passing(2), excluded))

    assert approved
    assert completeness == FULL_COMPLETENESS
    assert "B99-AC03 | N/A" in rendered


def test_non_applicable_criterion_without_justification_is_rejected(tmp_path: Path) -> None:
    excluded = '\n[[criteria]]\nid = "B99-AC03"\nmandatory = true\napplicable = false\n'
    manifest_path, _ = write(tmp_path, manifest(*passing(2), excluded))

    with pytest.raises(ValueError, match="justification"):
        load_manifest(manifest_path)


@pytest.mark.parametrize(
    ("justification", "expected"), [("Sin superficie observable", True), ("", False)]
)
def test_vc01_not_applicable_requires_justification(
    tmp_path: Path, justification: str, expected: bool
) -> None:
    content = manifest(*passing(3), vc01="NOT_APPLICABLE").replace(
        'status = "NOT_APPLICABLE"', f'status = "NOT_APPLICABLE"\njustification = "{justification}"'
    )

    approved, _, _ = report_for(tmp_path, content)

    assert approved is expected


def run_evidence(directory: Path, junit: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "quality.evidence", str(directory), f"--junit={junit}"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_command_fails_when_any_ticket_is_blocked(tmp_path: Path) -> None:
    _, junit = write(tmp_path, manifest(*passing(3)))
    (tmp_path / "B98.toml").write_text(
        manifest(criterion("B98-AC01", '"tests/test_sample.py::test_broken"')).replace("B99", "B98")
    )

    result = run_evidence(tmp_path, junit)

    assert result.returncode == 1
    assert "## B99: APROBADO" in result.stdout
    assert "## B98: BLOQUEADO" in result.stdout


def test_command_succeeds_when_every_ticket_is_approved(tmp_path: Path) -> None:
    _, junit = write(tmp_path, manifest(*passing(3)))

    result = run_evidence(tmp_path, junit)

    assert result.returncode == 0, result.stdout
