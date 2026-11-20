import argparse
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

from pydantic import BaseModel, ConfigDict, model_validator

THRESHOLD = 97


class Status(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    NOT_APPLICABLE = "N/A"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Case(StrictModel):
    id: str
    mode: Literal["automated", "manual", "external"]
    tests: tuple[str, ...] = ()
    result: Literal["PASS", "FAIL", "BLOCKED", "NOT_RUN"] = "NOT_RUN"
    evidence: str = ""


class Criterion(StrictModel):
    id: str
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
    status: Literal["PASS", "NOT_APPLICABLE", "NOT_RUN", "FAIL", "BLOCKED"]
    justification: str = ""


class Review(StrictModel):
    pending_findings: int


class Manifest(StrictModel):
    ticket: str
    vc01: Vc01
    review: Review
    criteria: tuple[Criterion, ...] = ()


def mandatory_label(criterion: Criterion) -> str:
    return "sí" if criterion.mandatory else "no"


@dataclass(frozen=True)
class CriterionResult:
    criterion: Criterion
    status: Status


@dataclass(frozen=True)
class Report:
    ticket: str
    results: tuple[CriterionResult, ...]
    completeness: float | None
    blockers: tuple[str, ...]

    @property
    def approved(self) -> bool:
        return not self.blockers

    def render(self) -> str:
        rows = [
            f"| {result.criterion.id} | {result.status} | {mandatory_label(result.criterion)} |"
            for result in self.results
        ]
        completeness = "inválida" if self.completeness is None else f"{self.completeness:.2f}%"
        verdict = "APROBADO" if self.approved else "BLOQUEADO"
        return "\n".join(
            [
                f"## {self.ticket}: {verdict}",
                "| AC | Estado | Obligatorio |",
                "| --- | --- | --- |",
                *rows,
                f"Completitud: {completeness}",
                *(f"- Bloqueo: {blocker}" for blocker in self.blockers),
            ]
        )


def load_manifest(path: Path) -> Manifest:
    with path.open("rb") as source:
        return Manifest.model_validate(tomllib.load(source))


def junit_key(classname: str, name: str) -> str:
    return f"{classname.replace('.', '/')}.py::{name}"


def read_junit(path: Path) -> dict[str, Status]:
    outcomes: dict[str, Status] = {}
    for case in ElementTree.parse(path).iter("testcase"):
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
        return recorded_status(case)
    statuses = [outcome_of(test, outcomes) for test in case.tests]
    if Status.FAIL in statuses:
        return Status.FAIL
    if not statuses or Status.NOT_RUN in statuses:
        return Status.NOT_RUN
    return Status.PASS


def recorded_status(case: Case) -> Status:
    if case.result == "PASS" and not case.evidence.strip():
        return Status.NOT_RUN
    return Status(case.result)


def criterion_status(criterion: Criterion, outcomes: dict[str, Status]) -> Status:
    if not criterion.applicable:
        return Status.NOT_APPLICABLE
    statuses = [case_status(case, outcomes) for case in criterion.cases]
    if not statuses:
        return Status.NOT_RUN
    for worst in (Status.FAIL, Status.BLOCKED, Status.NOT_RUN):
        if worst in statuses:
            return worst
    return Status.PASS


def evaluate(manifest: Manifest, outcomes: dict[str, Status]) -> Report:
    results = tuple(
        CriterionResult(criterion, criterion_status(criterion, outcomes))
        for criterion in manifest.criteria
    )
    applicable = [result for result in results if result.criterion.applicable]
    passed = sum(result.status is Status.PASS for result in applicable)
    completeness = 100 * passed / len(applicable) if applicable else None
    return Report(manifest.ticket, results, completeness, blockers(manifest, results, completeness))


def blockers(
    manifest: Manifest, results: tuple[CriterionResult, ...], completeness: float | None
) -> tuple[str, ...]:
    found: list[str] = []
    if completeness is None:
        found.append("sin criterios aplicables: completitud inválida")
    elif completeness < THRESHOLD:
        found.append(f"completitud {completeness:.2f}% por debajo de {THRESHOLD}%")
    found.extend(
        f"{result.criterion.id} obligatorio en {result.status}"
        for result in results
        if result.criterion.mandatory
        and result.criterion.applicable
        and result.status is not Status.PASS
    )
    if not vc01_satisfied(manifest.vc01):
        found.append(f"VC01 en {manifest.vc01.status}")
    if manifest.review.pending_findings:
        found.append(f"{manifest.review.pending_findings} hallazgos de review pendientes")
    return tuple(found)


def vc01_satisfied(vc01: Vc01) -> bool:
    return vc01.status == "PASS" or (
        vc01.status == "NOT_APPLICABLE" and bool(vc01.justification.strip())
    )


def manifests(location: Path) -> list[Path]:
    return sorted(location.glob("*.toml")) if location.is_dir() else [location]


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="quality.evidence")
    parser.add_argument("location", type=Path)
    parser.add_argument("--junit", type=Path, required=True)
    options = parser.parse_args(arguments)
    outcomes = read_junit(options.junit)
    reports = [evaluate(load_manifest(path), outcomes) for path in manifests(options.location)]
    for report in reports:
        print(report.render(), end="\n\n")
    if not reports:
        print(f"No evidence manifests found in {options.location}")
    return 0 if reports and all(report.approved for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
