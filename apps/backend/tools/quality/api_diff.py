import argparse
import json
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Change(StrEnum):
    TYPE = "type"
    REMOVED = "removed"
    ADDED = "added"
    VALUE = "value"


@dataclass(frozen=True)
class Difference:
    path: str
    kind: Change
    before: str | None
    after: str | None

    def __str__(self) -> str:
        return f"{self.kind}: {self.path}: {self.before} -> {self.after}"


def path_pattern(declared: str) -> re.Pattern[str]:
    return re.compile(re.escape(declared).replace(r"\[\*\]", r"\[\d+\]") + "$")


class Normalizer:
    def __init__(self, declared: Sequence[str]) -> None:
        self.patterns = [path_pattern(path) for path in declared]
        self.placeholders: dict[str, str] = {}

    def placeholder(self, value: object) -> str:
        key = json.dumps(value, sort_keys=True)
        if key not in self.placeholders:
            self.placeholders[key] = f"<normalized:{len(self.placeholders) + 1}>"
        return self.placeholders[key]

    def apply(self, value: object, path: str = "") -> object:
        if any(pattern.match(path) for pattern in self.patterns):
            return self.placeholder(value)
        if isinstance(value, dict):
            return {key: self.apply(item, join(path, str(key))) for key, item in value.items()}
        if isinstance(value, list):
            return [self.apply(item, f"{path}[{index}]") for index, item in enumerate(value)]
        return value


def join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def differences(before: object, after: object, path: str) -> Iterator[Difference]:
    if type(before) is not type(after):
        yield Difference(path, Change.TYPE, repr(before), repr(after))
    elif isinstance(before, dict) and isinstance(after, dict):
        for key in before:
            if key in after:
                yield from differences(before[key], after[key], join(path, key))
            else:
                yield Difference(join(path, key), Change.REMOVED, repr(before[key]), None)
        for key in after.keys() - before.keys():
            yield Difference(join(path, key), Change.ADDED, None, repr(after[key]))
    elif isinstance(before, list) and isinstance(after, list):
        for index in range(max(len(before), len(after))):
            item_path = f"{path}[{index}]"
            if index >= len(after):
                yield Difference(item_path, Change.REMOVED, repr(before[index]), None)
            elif index >= len(before):
                yield Difference(item_path, Change.ADDED, None, repr(after[index]))
            else:
                yield from differences(before[index], after[index], item_path)
    elif before != after:
        yield Difference(path, Change.VALUE, repr(before), repr(after))


def compare(baseline: object, current: object, normalized: Sequence[str]) -> list[Difference]:
    normalized_baseline = Normalizer(normalized).apply(baseline)
    normalized_current = Normalizer(normalized).apply(current)
    return list(differences(normalized_baseline, normalized_current, ""))


def main(arguments: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="quality.api_diff")
    parser.add_argument("baseline", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument("--normalize", action="append", default=[])
    options = parser.parse_args(arguments)
    baseline = json.loads(options.baseline.read_text())
    current = json.loads(options.current.read_text())
    found = compare(baseline, current, options.normalize)
    for difference in found:
        print(difference)
    if not found:
        print("No differences after declared normalization")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
