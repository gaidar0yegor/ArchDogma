"""Module-level import graph — the Tier 2 substrate.

Tier 1 asks "is this function too big?". It can never ask "does everything
in this system depend on one file that nobody dares change?", because that
question does not exist inside a single function body.

This module builds the structure that makes those questions askable:

    ImportGraph
        modules   name → ModuleNode        (one per .py file)
        edges     name → names it imports  (internal only)
        reverse   name → names importing it
        cycles    strongly connected components of size >= 2

Deliberate limits, stated up front so nobody mistakes this for a resolver:

  - Static imports only. `importlib.import_module(x)` and `__import__` are
    invisible here. A codebase that imports dynamically will look less
    coupled than it is. Tier 1's `dynamic-magic` tag is the honest hint
    that this graph is incomplete for that file.
  - Conditional imports (inside `if TYPE_CHECKING:`, inside functions) are
    collected the same as top-level ones. An edge means "this file names
    that module", not "this edge exists at runtime".
  - External packages are counted but not traversed. We know a module
    imports `requests`; we do not model what `requests` imports.

Standard library only — `ast` plus `pathlib`, per the project's no-heavy-
dependency posture.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImportRef:
    """One import statement, as written, before resolution.

    `module` is the dotted target: for `import a.b` it is "a.b"; for
    `from a.b import c` it is "a.b" with `names` holding ("c",). `level` is
    the number of leading dots in a relative import (0 for absolute).
    """

    module: str | None  # None for `from . import x`
    names: tuple[str, ...]
    level: int
    line: int
    col: int


@dataclass(frozen=True)
class ModuleNode:
    """One Python file, addressed by its importable dotted name."""

    name: str
    path: Path
    sloc: int
    def_count: int  # top-level `def` + `class` statements
    raw_imports: tuple[ImportRef, ...] = ()

    @property
    def is_package(self) -> bool:
        return self.path.name == "__init__.py"


@dataclass(frozen=True)
class ImportGraph:
    """Resolved import structure over a set of modules.

    `edges` and `reverse` hold internal edges only — an import that resolves
    to another module in this graph. `external` holds the top-level names of
    third-party / stdlib imports per module, which is enough to answer
    supply-chain questions without pretending to resolve them.
    """

    modules: dict[str, ModuleNode]
    edges: dict[str, tuple[str, ...]]
    reverse: dict[str, tuple[str, ...]]
    external: dict[str, tuple[str, ...]]
    cycles: tuple[tuple[str, ...], ...] = ()
    ambiguous_names: tuple[str, ...] = ()
    parse_errors: dict[str, str] = field(default_factory=dict)

    def afferent(self, name: str) -> int:
        """Ca — how many modules import this one."""
        return len(self.reverse.get(name, ()))

    def efferent(self, name: str) -> int:
        """Ce — how many internal modules this one imports."""
        return len(self.edges.get(name, ()))

    def instability(self, name: str) -> float:
        """I = Ce / (Ca + Ce), per Martin's package metrics.

        0.0 = maximally stable (everyone depends on it, it depends on
        nobody). 1.0 = maximally unstable. A module with no edges at all
        has no meaningful instability; we return 0.0 and callers are
        expected to gate on `Ca + Ce` before reading it.
        """
        ca, ce = self.afferent(name), self.efferent(name)
        total = ca + ce
        if total == 0:
            return 0.0
        return ce / total

    def cycle_for(self, name: str) -> tuple[str, ...] | None:
        """Return the cycle containing `name`, or None."""
        for cycle in self.cycles:
            if name in cycle:
                return cycle
        return None


# ---------------------------------------------------------------------------
# Module naming
# ---------------------------------------------------------------------------


def module_name_for(path: Path) -> str:
    """Derive the importable dotted name for a file from its package chain.

    Walks up while each directory holds `__init__.py`, so the name is the
    one an `import` statement would actually use — independent of whether
    the caller scanned the repo root, `src/`, or the package directory.

        src/archdogma/probe/graph.py  →  archdogma.probe.graph
        src/archdogma/__init__.py     →  archdogma
        scripts/release.py            →  release      (no package chain)

    A file outside any package gets its bare stem, which can collide.
    `build_graph` records those collisions in `ambiguous_names` rather than
    silently picking a winner for import resolution.
    """
    parts = [path.stem]
    if path.name == "__init__.py":
        parts = []

    parent = path.parent
    while (parent / "__init__.py").exists():
        parts.insert(0, parent.name)
        parent = parent.parent
        # Defensive: a filesystem root has itself as parent.
        if parent == parent.parent:
            break

    if not parts:
        # `__init__.py` in a directory with no `__init__.py` chain above it.
        return path.parent.name
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_imports(tree: ast.Module) -> tuple[ImportRef, ...]:
    """Collect every import statement anywhere in the file.

    Includes imports nested in functions, classes and `if` blocks. An import
    inside a function still creates a dependency between the two files; it
    just defers when the cost is paid.
    """
    refs: list[ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                refs.append(
                    ImportRef(
                        module=alias.name,
                        names=(),
                        level=0,
                        line=node.lineno,
                        col=node.col_offset,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            refs.append(
                ImportRef(
                    module=node.module,
                    names=tuple(a.name for a in node.names),
                    level=node.level or 0,
                    line=node.lineno,
                    col=node.col_offset,
                )
            )
    return tuple(refs)


def count_module_sloc(tree: ast.Module, source: str) -> int:
    """Source lines of code: non-blank, non-comment, excluding docstrings.

    Deliberately crude and stable — this feeds a threshold, not a report.
    """
    docstring_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                first = body[0].lineno
                last = body[0].end_lineno or first
                docstring_lines.update(range(first, last + 1))

    count = 0
    for i, line in enumerate(source.splitlines(), start=1):
        if i in docstring_lines:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def count_top_level_defs(tree: ast.Module) -> int:
    """Top-level `def`, `async def` and `class` statements."""
    return sum(
        1
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    )


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _resolve_relative(importer: str, ref: ImportRef, is_package: bool) -> str | None:
    """Turn a relative import into an absolute dotted prefix.

    `from . import x` inside `a.b.c` (a module) resolves against `a.b`.
    Inside `a.b` (a package `__init__`) it resolves against `a.b` itself,
    because a package's own directory is level 1.
    """
    base_parts = importer.split(".")
    if not is_package:
        base_parts = base_parts[:-1]
    # level 1 = current package; each extra dot climbs one more.
    climb = ref.level - 1
    if climb > len(base_parts):
        return None
    if climb:
        base_parts = base_parts[:-climb]
    if ref.module:
        base_parts = base_parts + ref.module.split(".")
    return ".".join(p for p in base_parts if p)


def _longest_known_prefix(dotted: str, known: set[str]) -> str | None:
    """Longest dotted prefix of `dotted` present in `known`.

    `import a.b.c` executes `a`, then `a.b`, then `a.b.c`. If the scan did
    not include `a.b.c` — a subset scan, or a name that is really a symbol —
    the dependency on the deepest package we do know about is still real.
    """
    parts = dotted.split(".")
    for stop in range(len(parts), 0, -1):
        candidate = ".".join(parts[:stop])
        if candidate in known:
            return candidate
    return None


def resolve_targets(
    importer: str,
    ref: ImportRef,
    is_package: bool,
    known: set[str],
) -> set[str]:
    """Internal modules this one import statement depends on.

    `from a.b import c, d` is the case that makes this non-trivial: each
    name may independently be a submodule or a symbol. Resolving only the
    first one — or collapsing the statement to a single edge — undercounts
    efferent coupling on exactly the wide re-export imports where coupling
    matters most. So every name is resolved on its own, and the package is
    added only when at least one name turned out to be a plain symbol.
    """
    if ref.level > 0:
        base = _resolve_relative(importer, ref, is_package)
    else:
        base = ref.module
    if not base:
        return set()

    if not ref.names:
        hit = _longest_known_prefix(base, known)
        return {hit} if hit else set()

    submodules = {f"{base}.{n}" for n in ref.names if f"{base}.{n}" in known}
    if submodules:
        # Names that did not resolve as modules are symbols living in `base`,
        # so the importer depends on `base` itself as well.
        if len(submodules) < len(ref.names) and base in known:
            submodules.add(base)
        return submodules

    hit = _longest_known_prefix(base, known)
    return {hit} if hit else set()


def _top_level_external(ref: ImportRef) -> str | None:
    """The distribution-ish top-level name for an unresolved absolute import."""
    if ref.level > 0 or not ref.module:
        return None
    return ref.module.split(".")[0]


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def find_cycles(edges: dict[str, tuple[str, ...]]) -> tuple[tuple[str, ...], ...]:
    """Strongly connected components of size >= 2, via iterative Tarjan.

    Iterative rather than recursive: a real dependency graph can be deeper
    than Python's recursion limit, and a crash while auditing someone's
    legacy monolith is exactly the wrong failure mode.

    Self-loops (`a` imports `a`) are excluded — they are a parse artifact of
    `__init__.py` re-exports far more often than a real cycle.
    """
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    counter = 0
    components: list[tuple[str, ...]] = []

    for root in sorted(edges):
        if root in index:
            continue

        # work stack holds (node, iterator position into its successors)
        work: list[tuple[str, int]] = [(root, 0)]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = True

        while work:
            node, edge_i = work[-1]
            successors = edges.get(node, ())
            if edge_i < len(successors):
                work[-1] = (node, edge_i + 1)
                nxt = successors[edge_i]
                if nxt == node:
                    continue
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack[nxt] = True
                    work.append((nxt, 0))
                elif on_stack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            else:
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component: list[str] = []
                    while True:
                        member = stack.pop()
                        on_stack[member] = False
                        component.append(member)
                        if member == node:
                            break
                    if len(component) >= 2:
                        components.append(tuple(sorted(component)))

    return tuple(sorted(components))


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph(paths: list[Path]) -> ImportGraph:
    """Build the import graph over a concrete list of Python files.

    Files that fail to parse are recorded in `parse_errors` and contribute
    no edges — a syntax error must not silently shrink the graph.
    """
    modules: dict[str, ModuleNode] = {}
    parse_errors: dict[str, str] = {}
    seen_names: dict[str, list[Path]] = defaultdict(list)

    for path in paths:
        name = module_name_for(path)
        seen_names[name].append(path)
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as e:
            parse_errors[str(path)] = str(e)
            continue
        modules[name] = ModuleNode(
            name=name,
            path=path,
            sloc=count_module_sloc(tree, source),
            def_count=count_top_level_defs(tree),
            raw_imports=extract_imports(tree),
        )

    ambiguous = tuple(sorted(n for n, ps in seen_names.items() if len(ps) > 1))

    edges: dict[str, list[str]] = {name: [] for name in modules}
    external: dict[str, list[str]] = {name: [] for name in modules}

    known = set(modules)
    for name, node in modules.items():
        internal_seen: set[str] = set()
        external_seen: set[str] = set()
        for ref in node.raw_imports:
            targets = resolve_targets(name, ref, node.is_package, known)
            # An ambiguous name cannot be attributed to one file, so it is
            # not allowed to create an edge. Silence beats a wrong arrow in
            # a dependency report. Self-edges are dropped for the same
            # reason they are dropped from cycles.
            targets = {t for t in targets if t != name and t not in ambiguous}
            if targets:
                internal_seen |= targets
                continue
            ext = _top_level_external(ref)
            if ext is not None:
                external_seen.add(ext)
        edges[name] = sorted(internal_seen)
        external[name] = sorted(external_seen)

    reverse: dict[str, list[str]] = {name: [] for name in modules}
    for importer, targets in edges.items():
        for target in targets:
            reverse[target].append(importer)

    frozen_edges = {k: tuple(v) for k, v in edges.items()}

    return ImportGraph(
        modules=modules,
        edges=frozen_edges,
        reverse={k: tuple(sorted(v)) for k, v in reverse.items()},
        external={k: tuple(v) for k, v in external.items()},
        cycles=find_cycles(frozen_edges),
        ambiguous_names=ambiguous,
        parse_errors=parse_errors,
    )
