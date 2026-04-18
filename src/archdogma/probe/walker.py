"""AST walker — traverses a Python function and collects signals.

v0.1-alpha3: supports top-level `def` / `async def`, class methods, and
nested functions. Addressed by qualified name:

    foo                      — top-level function
    MyClass.method           — method of a top-level class
    outer.inner              — nested function inside `outer`
    MyClass.method.inner     — nested function inside a method
    Outer.Inner.method       — method of a nested class

The dot is the only separator. Names are case-sensitive.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from archdogma.catalog.loader import Catalog, CandidateRef, DogmaRef
from archdogma.probe.tags.tier1 import TIER1_DETECTORS, Tag


# A FunctionDef-like node — used liberally in signatures to keep them honest.
FuncNode = ast.FunctionDef | ast.AsyncFunctionDef


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


@dataclass(frozen=True)
class DiscoveredFunction:
    """One addressable function in a file, with its qualified name and kind.

    `kind` is a small enumeration meant for human display, not dispatch:
        "function" — top-level def / async def
        "method"   — def inside a class body (direct or nested class)
        "nested"   — def inside another function
    """

    qualified_name: str
    node: FuncNode
    kind: str
    container: str | None  # qualified name of the enclosing scope, or None


def parse_file(path: Path) -> ast.Module:
    """Parse a Python file into an AST.

    Raises SyntaxError if the file is not valid Python.
    """
    source = path.read_text(encoding="utf-8")
    return ast.parse(source, filename=str(path))


def list_top_level_functions(tree: ast.Module) -> list[FuncNode]:
    """Return top-level function definitions, in source order.

    Kept narrow — callers that want class methods and nested functions
    should use `list_all_functions` instead.
    """
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def list_all_functions(tree: ast.Module) -> list[DiscoveredFunction]:
    """Walk the module and return every addressable function.

    Returns them in a stable order: source order, depth-first.
    Qualified names use `.` as the only separator. A method of a class
    is `ClassName.method`; a nested function is `outer_name.inner`.
    """
    out: list[DiscoveredFunction] = []
    _discover(tree.body, parent_qualified=None, parent_kind="module", out=out)
    return out


def _discover(
    stmts: list[ast.stmt],
    parent_qualified: str | None,
    parent_kind: str,  # "module" | "class" | "function"
    out: list[DiscoveredFunction],
) -> None:
    """Recursively collect function / method / nested defs in source order.

    `parent_kind` determines the DiscoveredFunction.kind emitted when we
    meet a FunctionDef at this level:
        module   → "function"
        class    → "method"
        function → "nested"
    """
    for node in stmts:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            qualified = (
                f"{parent_qualified}.{node.name}" if parent_qualified else node.name
            )
            kind = _kind_from_parent(parent_kind)
            out.append(
                DiscoveredFunction(
                    qualified_name=qualified,
                    node=node,
                    kind=kind,
                    container=parent_qualified,
                )
            )
            # Descend — nested defs and methods on inner classes both matter.
            _discover(node.body, qualified, "function", out)
        elif isinstance(node, ast.ClassDef):
            qualified = (
                f"{parent_qualified}.{node.name}" if parent_qualified else node.name
            )
            # Classes themselves aren't addressable as functions, but their
            # contents are. parent_kind becomes "class" so immediate defs
            # are tagged as "method".
            _discover(node.body, qualified, "class", out)
        # Any other statement: we could descend into if/for/etc to catch
        # conditionally defined functions, but that's deliberately out of
        # scope — a function buried in `if os.name == "nt":` isn't a
        # normal addressing target.


def _kind_from_parent(parent_kind: str) -> str:
    if parent_kind == "class":
        return "method"
    if parent_kind == "function":
        return "nested"
    return "function"


def find_function(tree: ast.Module, name: str) -> FuncNode | None:
    """Find a function by its qualified name.

    Accepts:
        "foo"                    — top-level def
        "MyClass.method"         — method
        "outer.inner"            — nested function
        "MyClass.method.inner"   — nested inside a method
        "Outer.Inner.method"     — method of a nested class

    Returns None if the path doesn't resolve. Bare names that happen to
    collide with a class attribute are not resolved — this function only
    returns FunctionDef / AsyncFunctionDef.
    """
    for discovered in list_all_functions(tree):
        if discovered.qualified_name == name:
            return discovered.node
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
