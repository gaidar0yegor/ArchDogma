"""AST walker — traverses a Python function and collects signals.

v0.1: supports top-level `def` / `async def`. Class methods and nested
functions are not yet addressable — next milestone.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from archdogma.catalog.loader import Catalog, CandidateRef, DogmaRef
from archdogma.probe.tags.tier1 import TIER1_DETECTORS, Tag


@dataclass(frozen=True)
class CatalogLink:
    """Connection between a detected tag and a catalog entry.

    Kept as a separate, flat record (not a reference to DogmaRef) so rendering
    is purely positional — no catalog re-lookup at print time.
    """

    tag_name: str
    entry_id: str
    entry_kind: str  # "dogma" | "candidate"
    entry_title: str
    entry_number: int | None  # dogmas have numbers, candidates don't


@dataclass(frozen=True)
class ProbeResult:
    """Result of probing one function."""

    file: Path
    function_name: str
    line_start: int
    line_end: int
    tags: tuple[Tag, ...] = field(default_factory=tuple)
    catalog_links: tuple[CatalogLink, ...] = field(default_factory=tuple)

    @property
    def loc(self) -> int:
        """Total lines occupied by the function definition (1-based inclusive)."""
        return self.line_end - self.line_start + 1


def parse_file(path: Path) -> ast.Module:
    """Parse a Python file into an AST.

    Raises SyntaxError if the file is not valid Python.
    """
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))


def list_top_level_functions(
    tree: ast.Module,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return top-level function definitions, in source order."""
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def find_function(
    tree: ast.Module, name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Find a top-level function by name. Does not descend into classes yet."""
    for node in list_top_level_functions(tree):
        if node.name == name:
            return node
    return None


def _build_catalog_links(
    tags: list[Tag], catalog: Catalog | None
) -> tuple[CatalogLink, ...]:
    """Resolve catalog entries for each tag. Empty if no catalog or no match."""
    if catalog is None:
        return ()
    links: list[CatalogLink] = []
    for tag in tags:
        entries = catalog.tag_index.get(tag.name, ())
        for entry in entries:
            links.append(_link_from_entry(tag.name, entry))
    return tuple(links)


def _link_from_entry(
    tag_name: str, entry: DogmaRef | CandidateRef
) -> CatalogLink:
    number = entry.number if isinstance(entry, DogmaRef) else None
    return CatalogLink(
        tag_name=tag_name,
        entry_id=entry.id,
        entry_kind=entry.kind,
        entry_title=entry.title,
        entry_number=number,
    )


def probe_function(
    path: Path,
    function_name: str,
    catalog: Catalog | None = None,
) -> ProbeResult | None:
    """Run all Tier 1 detectors against one function in `path`.

    If `catalog` is provided, also resolves catalog links for each tag.
    Returns None if the function is not found in the file.
    """
    tree = parse_file(path)
    func = find_function(tree, function_name)
    if func is None:
        return None

    tags: list[Tag] = []
    for _tag_name, detector in TIER1_DETECTORS:
        result = detector(func)  # type: ignore[operator]
        if result is not None:
            tags.append(result)

    return ProbeResult(
        file=path,
        function_name=function_name,
        line_start=func.lineno,
        line_end=func.end_lineno or func.lineno,
        tags=tuple(tags),
        catalog_links=_build_catalog_links(tags, catalog),
    )
