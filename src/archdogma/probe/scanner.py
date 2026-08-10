"""File and directory scanner — runs Tier 1 and Tier 2 probes over a tree."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from archdogma.catalog.loader import Catalog
from archdogma.probe.graph import ImportGraph, build_graph
from archdogma.probe.tags.tier1 import Tag
from archdogma.probe.tags.tier2 import TIER2_DETECTORS
from archdogma.probe.walker import (
    CatalogLink,
    ProbeResult,
    build_catalog_links,
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


# ---------------------------------------------------------------------------
# Tier 2 — module-level scan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModuleResult:
    """Tier 2 findings and metrics for one module.

    Metrics travel with the result even when no tag fired. A module at
    Ca=9 with the hub threshold at 10 is information; suppressing it
    because it did not cross a line turns a graph into a pass/fail light.
    """

    name: str
    file: Path
    sloc: int
    def_count: int
    afferent: int
    efferent: int
    instability: float
    tags: tuple[Tag, ...] = field(default_factory=tuple)
    catalog_links: tuple[CatalogLink, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ModuleScanResult:
    """Whole-project Tier 2 result: the graph plus per-module findings."""

    root: Path
    graph: ImportGraph
    modules: tuple[ModuleResult, ...]

    @property
    def tag_count(self) -> int:
        return sum(len(m.tags) for m in self.modules)

    @property
    def flagged(self) -> tuple[ModuleResult, ...]:
        return tuple(m for m in self.modules if m.tags)


def scan_modules(
    root: Path,
    catalog: Catalog | None = None,
    excludes: tuple[str, ...] = (),
) -> ModuleScanResult:
    """Build the import graph under `root` and run every Tier 2 detector.

    One pass: the graph is built once and shared by all detectors, because
    every Tier 2 question is a question about the same structure.
    """
    paths = list(collect_python_files(root, excludes))
    graph = build_graph(paths)

    results: list[ModuleResult] = []
    for name in sorted(graph.modules):
        node = graph.modules[name]
        tags: list[Tag] = []
        for _tag_name, detector in TIER2_DETECTORS:
            tags.extend(detector(name, graph))  # type: ignore[operator]
        results.append(
            ModuleResult(
                name=name,
                file=node.path,
                sloc=node.sloc,
                def_count=node.def_count,
                afferent=graph.afferent(name),
                efferent=graph.efferent(name),
                instability=graph.instability(name),
                tags=tuple(tags),
                catalog_links=build_catalog_links(tags, catalog),
            )
        )

    return ModuleScanResult(root=root, graph=graph, modules=tuple(results))
