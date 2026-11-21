import argparse
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

PYTHON = sys.executable
REPORTS = "reports"


@dataclass(frozen=True)
class Step:
    name: str
    command: tuple[str, ...]
    outputs: tuple[str, ...] = ()


STEPS = (
    Step("format", (PYTHON, "-m", "ruff", "format", "--check", ".")),
    Step("lint", (PYTHON, "-m", "ruff", "check", "--no-fix", ".")),
    Step("types", (PYTHON, "-m", "mypy")),
    Step("hygiene", (PYTHON, "-m", "quality.hygiene", "src", "tools", "tests")),
    Step("migrations", (PYTHON, "-m", "quality.migrations")),
    Step(
        "tests",
        (PYTHON, "-m", "pytest", f"--junitxml={REPORTS}/junit.xml"),
        outputs=(f"{REPORTS}/junit.xml",),
    ),
    Step("api", (PYTHON, "-m", "quality.api_snapshots")),
    Step(
        "evidence",
        (PYTHON, "-m", "quality.evidence", "../../docs/evidence", f"--junit={REPORTS}/junit.xml"),
    ),
)


def select_steps(names: str | None) -> list[Step]:
    if names is None:
        return list(STEPS)
    requested = names.split(",")
    known = {step.name: step for step in STEPS}
    unknown = sorted(set(requested) - known.keys())
    if unknown:
        raise SystemExit(f"Unknown steps: {', '.join(unknown)}")
    return [known[name] for name in requested]


def label(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def run_step(step: Step, project: Path) -> bool:
    for output in step.outputs:
        (project / output).unlink(missing_ok=True)
    print(f"--- {step.name}: {' '.join(step.command[1:])}", flush=True)
    completed = subprocess.run(step.command, cwd=project, check=False)  # noqa: S603
    passed = completed.returncode == 0
    print(f"{label(passed)} {step.name} (exit {completed.returncode})", flush=True)
    return passed


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="quality.check")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--steps")
    options = parser.parse_args(arguments)
    results = {step.name: run_step(step, options.project) for step in select_steps(options.steps)}
    failed = [name for name, passed in results.items() if not passed]
    print("Summary: " + ", ".join(f"{label(ok)} {name}" for name, ok in results.items()))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
