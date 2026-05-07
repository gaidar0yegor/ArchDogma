"""File and directory scanner — runs all Tier 1 probes on every Python file."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from archdogma.catalog.loader import Catalog
from archdogma.probe.walker import (
    ProbeResult,
    list_all_classes,
    list_all_functions,
    parse_file,
    probe_class,
    probe_function,
)


@dataclass(frozen=True)
class FileScanResult:
    """All probe results for one Python file."""

    file: Path
    results: tuple[ProbeResult, ...]
    parse_error: str | None = None

    @property
    def has_tags(self) -> bool:
        return any(r.tags for r in self.results)

    @property
    def tag_count(self) -> int:
        return sum(len(r.tags) for r in self.results)


# Directories to skip during recursive scan — common non-project dirs.
_SKIP_DIRS = frozenset({
    ".git", ".tox", ".venv", "venv", "env", "__pycache__",
    ".mypy_cache", "node_modules", "dist", "build", ".eggs",
    ".pytest_cache", ".ruff_cache",
})


def scan_file(path: Path, catalog: Catalog | None = None) -> FileScanResult:
    """Run all Tier 1 probes on every function and class in a Python file."""
    try:
        tree = parse_file(path)
    except SyntaxError as e:
        return FileScanResult(
            file=path,
            results=(),
            parse_error=f"line {e.lineno}: {e.msg}",
        )

    results: list[ProbeResult] = []

    for df in list_all_functions(tree):
        result = probe_function(path, df.qualified_name, catalog=catalog)
        if result is not None:
            results.append(result)

    for cls in list_all_classes(tree):
        result = probe_class(path, cls.name, catalog=catalog)
        if result is not None:
            results.append(result)

    return FileScanResult(file=path, results=tuple(results))


def collect_python_files(
    root: Path,
    excludes: tuple[str, ...] = (),
) -> Iterator[Path]:
    """Yield .py files under root, skipping common non-project directories.

    `excludes` is a tuple of fnmatch glob patterns applied to the path
    relative to root (e.g. ``("tests/**", "*_pb2.py")``).
    """
    import fnmatch

    if root.is_file():
        if root.suffix == ".py":
            yield root
        return

    for path in sorted(root.rglob("*.py")):
        rel_parts = path.relative_to(root).parts
        # Skip if any parent directory component is in the skip set or ends
        # with ".egg-info" (editable installs).
        if any(
            p in _SKIP_DIRS or p.endswith(".egg-info")
            for p in rel_parts[:-1]
        ):
            continue
        rel = str(path.relative_to(root))
        if any(fnmatch.fnmatch(rel, pat) for pat in excludes):
            continue
        yield path


def scan_path(
    root: Path,
    catalog: Catalog | None = None,
    excludes: tuple[str, ...] = (),
) -> Iterator[FileScanResult]:
    """Scan every Python file under root, yielding one FileScanResult per file."""
    for py_file in collect_python_files(root, excludes):
        yield scan_file(py_file, catalog=catalog)
