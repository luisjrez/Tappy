import subprocess
import sys
from pathlib import Path

from quality.hygiene import Finding, find_comments

SOURCE_WITH_COMMENT_AND_HASH_STRING = """CHANNEL = "#cobros"
PATTERN = r"[#]{2}"


def label() -> str:
    # explains the obvious
    return f"{CHANNEL} #{PATTERN}"
"""


def run_hygiene(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "quality.hygiene", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_flags_comments_but_not_hash_inside_strings(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(SOURCE_WITH_COMMENT_AND_HASH_STRING)

    findings = find_comments(source)

    assert findings == [Finding(path=source, line=6, text="# explains the obvious")]


def test_allows_localized_tool_directives(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(
        "import os  # noqa: F401\n"
        "VALUE: int = os.environ  # type: ignore[assignment]\n"
        "def unreachable() -> None:  # pragma: no cover\n"
        "    pass\n"
    )

    assert find_comments(source) == []


def test_command_fails_and_lists_comment_locations(tmp_path: Path) -> None:
    package = tmp_path / "package"
    package.mkdir()
    (package / "clean.py").write_text('MESSAGE = "# not a comment"\n')
    (package / "commented.py").write_text("VALUE = 1\n# TODO remove\n")
    ignored = tmp_path / ".venv"
    ignored.mkdir()
    (ignored / "vendor.py").write_text("# third party\n")

    result = run_hygiene(tmp_path)

    assert result.returncode == 1
    assert f"{package / 'commented.py'}:2: # TODO remove" in result.stdout
    assert "clean.py" not in result.stdout
    assert "vendor.py" not in result.stdout


def test_command_succeeds_without_comments(tmp_path: Path) -> None:
    (tmp_path / "clean.py").write_text('MESSAGE = "# not a comment"\n')

    result = run_hygiene(tmp_path)

    assert result.returncode == 0
