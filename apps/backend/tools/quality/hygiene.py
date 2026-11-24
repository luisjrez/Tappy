import re
import sys
import tokenize
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

TOOL_DIRECTIVE = re.compile(r"#\s*(noqa: [A-Z0-9, ]+|type: ignore\[[\w, -]+\]|pragma: no cover)$")
EXCLUDED_DIRECTORIES = frozenset({".venv", "venv", "__pycache__", ".mypy_cache", ".ruff_cache"})


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.text}"


def find_comments(path: Path) -> list[Finding]:
    with path.open("rb") as source:
        return [
            Finding(path=path, line=token.start[0], text=token.string)
            for token in tokenize.tokenize(source.readline)
            if token.type == tokenize.COMMENT and not TOOL_DIRECTIVE.match(token.string)
        ]


def python_files(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for candidate in candidates:
            if not EXCLUDED_DIRECTORIES.intersection(candidate.parts):
                yield candidate


def main(arguments: Sequence[str]) -> int:
    findings = [
        finding
        for path in python_files(Path(argument) for argument in arguments)
        for finding in find_comments(path)
    ]
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
