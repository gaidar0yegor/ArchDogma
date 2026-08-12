"""File and directory scanner — runs Tier 1 and Tier 2 probes over a tree."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from archdogma.catalog.loader import Catalog
from archdogma.history import RepoHistory, load_history
from archdogma.probe.graph import ImportGraph, build_graph
from archdogma.probe.tags.tier1 import Tag
from archdogma.probe.tags.tier2 import TIER2_DETECTORS
from archdogma.probe.tags.tier3 import TIER3_DETECTORS
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
# Virtualenvs are ALSO detected by their pyvenv.cfg marker (see
# _is_virtualenv), because the name list can never be complete: the first
# field report was a scan grinding through 4,919 third-party files in a
# `.tool_venv/` that no list had thought to include.
_SKIP_DIRS = frozenset({
    ".git", ".tox", ".venv", "venv", "env", ".env", ".tool_venv",
    ".direnv", "__pycache__", ".mypy_cache", "node_modules", "dist",
    "build", ".eggs", ".pytest_cache", ".ruff_cache", ".nox",
})


def _is_virtualenv(path: Path) -> bool:
    """A directory containing pyvenv.cfg is a virtual environment,
    whatever it is named. The marker is written by venv and virtualenv
    alike, so it catches every naming convention the skip list misses."""
    return (path / "pyvenv.cfg").is_file()


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
    import os

    if root.is_file():
        if root.suffix == ".py":
            yield root
        return

    def _excluded(rel: str) -> bool:
        # fnmatch is not path-aware ("*" crosses "/"), so a bare directory
        # pattern like ".tool_venv" would silently match nothing under it.
        # Treat every pattern as also matching anything beneath it — the
        # behaviour every user of --exclude actually expects.
        for pat in excludes:
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.rstrip("/") + "/*"):
                return True
        return False

    # os.walk with in-place pruning, not rglob: a skipped virtualenv must
    # not even be walked. On a tree with a 5,000-file venv the difference
    # is the scan versus the coffee break.
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        rel_dir = "" if here == root else str(here.relative_to(root))
        dirnames[:] = [
            d
            for d in sorted(dirnames)
            if d not in _SKIP_DIRS
            and not d.endswith(".egg-info")
            and not _is_virtualenv(here / d)
            and not _excluded(f"{rel_dir}/{d}" if rel_dir else d)
        ]
        for name in sorted(filenames):
            if not name.endswith(".py"):
                continue
            rel = f"{rel_dir}/{name}" if rel_dir else name
            if _excluded(rel):
                continue
            yield here / name


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
    # Tier 3 — None when no git history was available for this file.
    commits: int | None = None
    days_since_change: int | None = None
    author_count: int | None = None


@dataclass(frozen=True)
class ModuleScanResult:
    """Whole-project module result: the graph, the history, and the findings.

    `history` is None when the scan ran outside a git work tree. Callers are
    expected to say so rather than present Tier 3 silence as a clean bill.
    """

    root: Path
    graph: ImportGraph
    modules: tuple[ModuleResult, ...]
    history: RepoHistory | None = None

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
    use_history: bool = True,
) -> ModuleScanResult:
    """Build the import graph under `root`, then run Tier 2 and Tier 3.

    One pass over the tree and one `git log` call: the graph and the history
    are each built once and shared by every detector, because every question
    at these tiers is a question about the same two structures.

    `use_history=False` forces Tier 3 off — useful when a caller wants a
    result that depends only on the working tree.
    """
    paths = list(collect_python_files(root, excludes))
    graph = build_graph(paths)
    history = load_history(root) if use_history else None

    results: list[ModuleResult] = []
    for name in sorted(graph.modules):
        node = graph.modules[name]
        tags: list[Tag] = []
        for _tag_name, detector in TIER2_DETECTORS:
            tags.extend(detector(name, graph))  # type: ignore[operator]
        for _tag_name, detector in TIER3_DETECTORS:
            tags.extend(detector(name, graph, history))  # type: ignore[operator]

        entry = history.for_path(node.path) if history else None
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
                commits=entry.commits if entry else None,
                days_since_change=(
                    history.days_since_change(node.path) if history else None
                ),
                author_count=entry.author_count if entry else None,
            )
        )

    return ModuleScanResult(
        root=root, graph=graph, modules=tuple(results), history=history
    )
