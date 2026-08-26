#!/usr/bin/env python3
"""Prune a domain-list-community data directory down to the include closure
of the given root lists, so the Go builder emits only the sections the
routing profiles actually reference instead of the whole upstream database.

Usage: prune-data.py <data-dir> <root> [<root> ...]
"""

import sys
from pathlib import Path


def closure(data_dir: Path, roots: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        path = data_dir / name
        if not path.is_file():
            print(f"Warning: included list {name} has no file", file=sys.stderr)
            continue
        seen.add(name)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("include:"):
                stack.append(line[len("include:"):].split()[0])
    return seen


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    data_dir = Path(sys.argv[1])
    keep = closure(data_dir, sys.argv[2:])
    removed = 0
    for path in sorted(data_dir.iterdir()):
        if path.is_file() and path.name not in keep:
            path.unlink()
            removed += 1
    print(f"kept {len(keep)} lists, removed {removed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
