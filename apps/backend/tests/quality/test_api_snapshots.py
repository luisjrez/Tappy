import json
import os
import subprocess
import sys
from pathlib import Path

CASES = """
[[cases]]
name = "health"
method = "GET"
path = "/health"
database = "unreachable"
"""
APPROVED_HEALTH = {
    "revision": "9f53aa9",
    "status": 200,
    "headers": {"content-type": "application/json"},
    "body": {"status": "ok", "environment": "contract"},
}


def contracts(tmp_path: Path, baseline: dict[str, object] | None) -> Path:
    directory = tmp_path / "contracts"
    (directory / "baselines").mkdir(parents=True)
    (directory / "cases.toml").write_text(CASES)
    if baseline is not None:
        (directory / "baselines" / "health.json").write_text(json.dumps(baseline))
    return directory


def run_snapshots(contracts_dir: Path, reports_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "quality.api_snapshots",
            f"--contracts={contracts_dir}",
            f"--reports={reports_dir}",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_matching_baseline_passes_and_keeps_current_artifact(tmp_path: Path) -> None:
    contracts_dir = contracts(tmp_path, APPROVED_HEALTH)

    result = run_snapshots(contracts_dir, tmp_path / "reports")

    current = json.loads((tmp_path / "reports" / "health.current.json").read_text())
    assert result.returncode == 0, result.stdout + result.stderr
    assert current["body"] == {"status": "ok", "environment": "contract"}
    assert "health: no differences against 9f53aa9" in result.stdout


def test_unexpected_difference_fails_without_touching_baseline(tmp_path: Path) -> None:
    contracts_dir = contracts(tmp_path, {**APPROVED_HEALTH, "body": {"status": "degraded"}})
    baseline_path = contracts_dir / "baselines" / "health.json"
    original = baseline_path.read_bytes()

    result = run_snapshots(contracts_dir, tmp_path / "reports")

    diff = (tmp_path / "reports" / "health.diff.txt").read_text()
    assert result.returncode == 1
    assert "body.status" in diff
    assert "body.environment" in diff
    assert baseline_path.read_bytes() == original


def test_missing_baseline_fails_and_is_not_created(tmp_path: Path) -> None:
    contracts_dir = contracts(tmp_path, None)

    result = run_snapshots(contracts_dir, tmp_path / "reports")

    assert result.returncode == 1
    assert "no approved baseline" in result.stdout
    assert not (contracts_dir / "baselines" / "health.json").exists()
    assert (tmp_path / "reports" / "health.current.json").exists()


def test_baseline_without_revision_is_rejected(tmp_path: Path) -> None:
    unversioned = {key: value for key, value in APPROVED_HEALTH.items() if key != "revision"}
    contracts_dir = contracts(tmp_path, unversioned)

    result = run_snapshots(contracts_dir, tmp_path / "reports")

    assert result.returncode == 1
    assert "revision" in result.stdout


def test_reports_from_previous_runs_are_cleared(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "removed-case.diff.txt").write_text("stale")

    run_snapshots(contracts(tmp_path, APPROVED_HEALTH), reports_dir)

    assert not (reports_dir / "removed-case.diff.txt").exists()


def test_unsafe_test_server_is_reported_without_traceback(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    (contracts_dir / "baselines").mkdir(parents=True)
    (contracts_dir / "cases.toml").write_text(CASES.replace("unreachable", "migrated"))

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "quality.api_snapshots",
            f"--contracts={contracts_dir}",
            f"--reports={tmp_path / 'reports'}",
        ],
        env={key: value for key, value in os.environ.items() if key != "TAPPY_TEST_DATABASE_URL"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 1
    assert "TAPPY_TEST_DATABASE_URL" in result.stderr
    assert "Traceback" not in result.stderr
