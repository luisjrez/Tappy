import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
FIXTURE_STEPS = "format,lint,types,hygiene,tests"
VALID_MODULE = 'def greeting(name: str) -> str:\n    return f"Hola {name}"\n'
VALID_TEST = (
    "from tappy.sample import greeting\n\n\n"
    "def test_greeting() -> None:\n"
    '    assert greeting("Ana") == "Hola Ana"\n'
)
INFRACTIONS = {
    "format": ("src/tappy/sample.py", "def greeting(name: str)->str:\n    return 'Hola '+name\n"),
    "lint": ("src/tappy/sample.py", VALID_MODULE + "\n\nimport os\n"),
    "types": (
        "src/tappy/sample.py",
        'def greeting(name: str) -> int:\n    return f"Hola {name}"\n',
    ),
    "hygiene": ("src/tappy/sample.py", "# greets people\n" + VALID_MODULE),
    "tests": ("tests/test_sample.py", VALID_TEST.replace('"Hola Ana"', '"Adiós Ana"')),
}


def build_fixture_project(root: Path) -> Path:
    project = root / "project"
    caches = shutil.ignore_patterns("__pycache__")
    (project / "tests").mkdir(parents=True)
    shutil.copy(BACKEND / "pyproject.toml", project / "pyproject.toml")
    shutil.copytree(BACKEND / "src", project / "src", ignore=caches)
    shutil.copytree(BACKEND / "tools", project / "tools", ignore=caches)
    (project / "src" / "tappy" / "sample.py").write_text(VALID_MODULE)
    (project / "tests" / "__init__.py").write_text("")
    (project / "tests" / "test_sample.py").write_text(VALID_TEST)
    return project


def run_check(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "quality.check",
            "--project",
            str(project),
            "--steps",
            FIXTURE_STEPS,
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def test_clean_project_passes_every_step(tmp_path: Path) -> None:
    result = run_check(build_fixture_project(tmp_path))

    assert result.returncode == 0, result.stdout + result.stderr
    for step in FIXTURE_STEPS.split(","):
        assert f"PASS {step}" in result.stdout


@pytest.mark.parametrize("step", INFRACTIONS)
def test_each_infraction_fails_the_battery(tmp_path: Path, step: str) -> None:
    project = build_fixture_project(tmp_path)
    relative_path, broken_source = INFRACTIONS[step]
    (project / relative_path).write_text(broken_source)

    result = run_check(project)

    assert result.returncode != 0
    assert f"FAIL {step}" in result.stdout
