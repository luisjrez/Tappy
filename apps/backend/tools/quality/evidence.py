import argparse
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, Field, model_validator

THRESHOLD = 97


class Status(StrEnum):
    PASS = "PASS"  # noqa: S105
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


class ReviewVerdict(StrEnum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"


NOT_APPLICABLE = "N/A"
SEVERITY = (Status.FAIL, Status.BLOCKED, Status.NOT_RUN)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Case(StrictModel):
    id: str
    mode: Literal["automated", "manual", "external"]
    tests: tuple[str, ...] = ()
    result: Status = Status.NOT_RUN
    evidence: str = ""


class Criterion(StrictModel):
    id: str
    use_cases: tuple[str, ...] = Field(min_length=1)
    mandatory: bool
    applicable: bool = True
    justification: str = ""
    cases: tuple[Case, ...] = ()

    @model_validator(mode="after")
    def require_justification_when_excluded(self) -> Criterion:
        if not self.applicable and not self.justification.strip():
            raise ValueError(f"{self.id}: a non-applicable criterion needs a justification")
        return self


class Vc01(StrictModel):
    status: Status
    modality: Literal["initial", "comparison", "not_applicable"]
    evidence: str = ""
    justification: str = ""


class Review(StrictModel):
    standards: ReviewVerdict
    spec: ReviewVerdict
    pending_findings: int = Field(ge=0)


class Manifest(StrictModel):
    ticket: str
    revision: str = Field(min_length=7)
    vc01: Vc01
    review: Review
    criteria: tuple[Criterion, ...] = ()


@dataclass(frozen=True)
class CaseResult:
    case: Case
    status: Status


@dataclass(frozen=True)
class CriterionResult:
    criterion: Criterion
    cases: tuple[CaseResult, ...]

    @property
    def status(self) -> Status | None:
        if not self.criterion.applicable:
            return None
        statuses = [result.status for result in self.cases]
        if not statuses:
            return Status.NOT_RUN
        return next((worst for worst in SEVERITY if worst in statuses), Status.PASS)

    def rows(self) -> list[str]:
        use_cases = ", ".join(self.criterion.use_cases)
        mandatory = "yes" if self.criterion.mandatory else "no"
        prefix = f"| {use_cases} | {self.criterion.id}"
        if self.status is None:
            return [f"{prefix} | - | {NOT_APPLICABLE} | {mandatory} |"]
        if not self.cases:
            return [f"{prefix} | - | {self.status} | {mandatory} |"]
        return [
            f"{prefix} | {result.case.id} | {result.status} | {mandatory} |"
            for result in self.cases
        ]


@dataclass(frozen=True)
class Report:
    ticket: str
    revision: str
    results: tuple[CriterionResult, ...]
    completeness: float | None
    blockers: tuple[str, ...]

    @property
    def approved(self) -> bool:
        return not self.blockers

    def render(self) -> str:
        completeness = "invalid" if self.completeness is None else f"{self.completeness:.2f}%"
        verdict = "APPROVED" if self.approved else "BLOCKED"
        return "\n".join(
            [
                f"## {self.ticket}: {verdict} (revision {self.revision})",
                "| UC | AC | TC | Status | Mandatory |",
                "| --- | --- | --- | --- | --- |",
                *(row for result in self.results for row in result.rows()),
                f"Completeness: {completeness}",
                *(f"- Blocker: {blocker}" for blocker in self.blockers),
            ]
        )


def load_manifest(path: Path) -> Manifest:
    with path.open("rb") as source:
        return Manifest.model_validate(tomllib.load(source))


def junit_key(classname: str, name: str) -> str:
    return f"{classname.replace('.', '/')}.py::{name}"


def read_junit(path: Path) -> dict[str, Status]:
    outcomes: dict[str, Status] = {}
    for case in ElementTree.parse(path).iter("testcase"):  # noqa: S314
        failed = any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
        key = junit_key(case.get("classname", ""), case.get("name", ""))
        outcomes[key] = Status.FAIL if failed else Status.PASS
    return outcomes


def outcome_of(test: str, outcomes: dict[str, Status]) -> Status:
    matches = [
        status for key, status in outcomes.items() if key == test or key.startswith(f"{test}[")
    ]
    if not matches:
        return Status.NOT_RUN
    return Status.FAIL if Status.FAIL in matches else Status.PASS


def case_status(case: Case, outcomes: dict[str, Status]) -> Status:
    if case.mode != "automated":
        if case.result is Status.PASS and not case.evidence.strip():
            return Status.NOT_RUN
        return case.result
    statuses = [outcome_of(test, outcomes) for test in case.tests]
    if Status.FAIL in statuses:
        return Status.FAIL
    if not statuses or Status.NOT_RUN in statuses:
        return Status.NOT_RUN
    return Status.PASS


def evaluate(
    manifest: Manifest, outcomes: dict[str, Status], revision_exists: Callable[[str], bool]
) -> Report:
    results = tuple(
        CriterionResult(
            criterion,
            tuple(CaseResult(case, case_status(case, outcomes)) for case in criterion.cases),
        )
        for criterion in manifest.criteria
    )
    applicable = [result for result in results if result.criterion.applicable]
    passed = sum(result.status is Status.PASS for result in applicable)
    completeness = 100 * passed / len(applicable) if applicable else None
    found = blockers(manifest, applicable, completeness, revision_exists)
    return Report(manifest.ticket, manifest.revision, results, completeness, found)


def blockers(
    manifest: Manifest,
    applicable: Sequence[CriterionResult],
    completeness: float | None,
    revision_exists: Callable[[str], bool],
) -> tuple[str, ...]:
    found: list[str] = []
    if completeness is None:
        found.append("no applicable criteria: completeness is invalid")
    elif completeness < THRESHOLD:
        found.append(f"completeness {completeness:.2f}% is below {THRESHOLD}%")
    found.extend(
        f"mandatory {result.criterion.id} is {result.status}"
        for result in applicable
        if result.criterion.mandatory and result.status is not Status.PASS
    )
    found.extend(vc01_problems(manifest.vc01))
    found.extend(review_problems(manifest.review))
    if not revision_exists(manifest.revision):
        found.append(f"revision {manifest.revision} is not in the repository history")
    return tuple(found)


def vc01_problems(vc01: Vc01) -> list[str]:
    if vc01.status is not Status.PASS:
        return [f"VC01 is {vc01.status}"]
    if vc01.modality == "not_applicable" and not vc01.justification.strip():
        return ["VC01 not applicable without justification"]
    if vc01.modality != "not_applicable" and not vc01.evidence.strip():
        return ["VC01 passed without evidence"]
    return []


def review_problems(review: Review) -> list[str]:
    problems = [
        f"{axis} review is {verdict}"
        for axis, verdict in (("standards", review.standards), ("spec", review.spec))
        if verdict is not ReviewVerdict.APPROVED
    ]
    if review.pending_findings:
        problems.append(f"{review.pending_findings} review findings pending")
    return problems


def revision_in_history(revision: str) -> bool:
    git = shutil.which("git")
    if git is None:
        return False
    completed = subprocess.run(  # noqa: S603
        [git, "merge-base", "--is-ancestor", revision, "HEAD"], capture_output=True, check=False
    )
    return completed.returncode == 0


def manifests(location: Path) -> list[Path]:
    return sorted(location.glob("*.toml")) if location.is_dir() else [location]


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="quality.evidence")
    parser.add_argument("location", type=Path)
    parser.add_argument("--junit", type=Path, required=True)
    options = parser.parse_args(arguments)
    outcomes = read_junit(options.junit)
    reports = [
        evaluate(load_manifest(path), outcomes, revision_in_history)
        for path in manifests(options.location)
    ]
    for report in reports:
        print(report.render(), end="\n\n")
    if not reports:
        print(f"No evidence manifests found in {options.location}")
    return 0 if reports and all(report.approved for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
