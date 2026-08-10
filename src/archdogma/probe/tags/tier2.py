"""Tier 2 tag detectors — module-level, cross-file, still no git and no runtime.

Tier 1 answers questions about one function. Tier 2 answers questions that
only exist once you have more than one file:

    - circular-import      ← implemented
    - hub-module           ← implemented
    - god-module           ← implemented
    - unstable-dependency  ← implemented

The detector protocol differs from Tier 1 by necessity: a module-level
signal needs the whole graph, not one node. Each detector takes
`(name, graph)` and returns a list of Tags — a module can be in exactly one
cycle but can violate stable-dependency against several targets at once.

On thresholds, the same rule as Tier 1 applies: no default here is
research-proven. They are starting points chosen to be quiet on small
projects and loud on the shapes the catalog has postmortems for. Every one
is a keyword argument so a project can disagree in its own terms.
"""

from __future__ import annotations

from archdogma.probe.graph import ImportGraph
from archdogma.probe.tags.tier1 import Tag

# Defaults. See module docstring — these are conventions, not findings.
DEFAULT_HUB_AFFERENT = 10
DEFAULT_GOD_MODULE_SLOC = 600
DEFAULT_GOD_MODULE_DEFS = 20
DEFAULT_STABLE_CEILING = 0.3
DEFAULT_INSTABILITY_GAP = 0.4
DEFAULT_SDP_MIN_DEGREE = 3


# ---------------------------------------------------------------------------
# circular-import
# ---------------------------------------------------------------------------
#
# Two or more modules that transitively import each other. Python tolerates
# many of these at runtime — until import order changes and a half-initialised
# module raises AttributeError in production but not in the test suite.
#
# The deeper reading is architectural: a cycle means the boundary between
# those modules is not real. Whatever layering the codebase claims, these
# files are one unit that has been split across several.


def detect_circular_import(name: str, graph: ImportGraph) -> list[Tag]:
    """Flag a module participating in an import cycle."""
    cycle = graph.cycle_for(name)
    if cycle is None:
        return []

    node = graph.modules.get(name)
    others = [m for m in cycle if m != name]

    # Point at the import that reaches back into the cycle, when we can find
    # one — a line number is worth more than a module name to whoever has to
    # break the loop.
    line, col = 1, 0
    if node is not None:
        in_cycle = set(cycle)
        for ref in node.raw_imports:
            module = ref.module or ""
            if any(module.startswith(other.split(".")[0]) for other in in_cycle):
                line, col = ref.line, ref.col
                break

    members = ", ".join(others[:4])
    if len(others) > 4:
        members += f", +{len(others) - 4} more"
    return [
        Tag(
            name="circular-import",
            detail=(
                f"Module is in an import cycle of {len(cycle)} modules "
                f"(with {members}). These files cannot be understood, "
                f"tested, or extracted independently."
            ),
            line=line,
            col=col,
        )
    ]


# ---------------------------------------------------------------------------
# hub-module
# ---------------------------------------------------------------------------
#
# High afferent coupling: a large share of the system imports this one file.
# Not a defect by itself — every project has a legitimate core. It becomes
# one when the hub keeps absorbing responsibilities, because every absorbed
# concern is now transitively depended on by everything.
#
# This is the shape behind the catalog's DRY case: an abstraction extracted
# after two similar call sites, then grown to serve four diverging
# subsystems, until a change made for one broke another.


def detect_hub_module(
    name: str,
    graph: ImportGraph,
    threshold: int = DEFAULT_HUB_AFFERENT,
) -> list[Tag]:
    """Flag a module that a large number of other modules import."""
    ca = graph.afferent(name)
    if ca < threshold:
        return []
    total = len(graph.modules)
    share = (ca / total * 100) if total else 0.0
    return [
        Tag(
            name="hub-module",
            detail=(
                f"{ca} modules import this one ({share:.0f}% of the project). "
                f"Every change here is a change to {ca} dependents; every "
                f"concern added here is inherited by all of them."
            ),
            line=1,
            col=0,
        )
    ]


# ---------------------------------------------------------------------------
# god-module
# ---------------------------------------------------------------------------
#
# The file-level counterpart of god-class: enough code and enough top-level
# definitions that the file has stopped being about one thing. Both signals
# are required — a 900-line file holding one long generated table is not the
# same problem as a 900-line file holding 40 unrelated helpers.


def detect_god_module(
    name: str,
    graph: ImportGraph,
    sloc_threshold: int = DEFAULT_GOD_MODULE_SLOC,
    def_threshold: int = DEFAULT_GOD_MODULE_DEFS,
) -> list[Tag]:
    """Flag a module that is large in both size and number of definitions."""
    node = graph.modules.get(name)
    if node is None:
        return []
    if node.sloc < sloc_threshold or node.def_count < def_threshold:
        return []
    return [
        Tag(
            name="god-module",
            detail=(
                f"{node.sloc} SLOC across {node.def_count} top-level "
                f"definitions. A file this wide has no single reason to "
                f"change, so every reason to change lands in it."
            ),
            line=1,
            col=0,
        )
    ]


# ---------------------------------------------------------------------------
# unstable-dependency
# ---------------------------------------------------------------------------
#
# Robert Martin's Stable Dependencies Principle: depend in the direction of
# stability. Instability I = Ce / (Ca + Ce). A module many others rely on
# (low I) that reaches out to a volatile module (high I) has imported that
# volatility on behalf of all its dependents.
#
# Gated on degree, because I is meaningless for a module with one edge:
# a file with Ce=1, Ca=0 scores a perfect 1.0 instability and says nothing.


def detect_unstable_dependency(
    name: str,
    graph: ImportGraph,
    stable_ceiling: float = DEFAULT_STABLE_CEILING,
    gap: float = DEFAULT_INSTABILITY_GAP,
    min_degree: int = DEFAULT_SDP_MIN_DEGREE,
) -> list[Tag]:
    """Flag a stable module that depends on a markedly less stable one."""
    own_degree = graph.afferent(name) + graph.efferent(name)
    if own_degree < min_degree:
        return []

    own_i = graph.instability(name)
    if own_i > stable_ceiling:
        return []

    node = graph.modules.get(name)
    import_lines: dict[str, tuple[int, int]] = {}
    if node is not None:
        for ref in node.raw_imports:
            if ref.module:
                import_lines.setdefault(ref.module, (ref.line, ref.col))

    tags: list[Tag] = []
    for target in graph.edges.get(name, ()):
        if graph.afferent(target) + graph.efferent(target) < min_degree:
            continue
        target_i = graph.instability(target)
        if target_i - own_i < gap:
            continue
        line, col = import_lines.get(target, (1, 0))
        tags.append(
            Tag(
                name="unstable-dependency",
                detail=(
                    f"Stable module (I={own_i:.2f}, {graph.afferent(name)} "
                    f"dependents) imports {target} (I={target_i:.2f}). "
                    f"Churn in {target} propagates to everything that "
                    f"depends on this module."
                ),
                line=line,
                col=col,
            )
        )
    return tags


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
#
# Parallel to TIER1_DETECTORS, but the callables take (name, graph) and
# return a list — module-level signals are not one-per-module the way a
# function-level threshold check is.

TIER2_DETECTORS: tuple[tuple[str, "object"], ...] = (
    ("circular-import", detect_circular_import),
    ("hub-module", detect_hub_module),
    ("god-module", detect_god_module),
    ("unstable-dependency", detect_unstable_dependency),
)
