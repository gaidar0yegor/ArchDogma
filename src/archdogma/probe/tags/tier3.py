"""Tier 3 tag detectors — code structure crossed with change history.

    - load-bearing-wall  ← implemented
    - churn-hotspot      ← implemented
    - single-author-hub  ← implemented
    - temporal-coupling  ← implemented

Tier 2 knows that forty modules import `core.py`. Tier 3 knows that nobody
has changed `core.py` in three years. Neither fact is alarming alone; taken
together they describe the specific thing every engineer inheriting a legacy
system is looking for and cannot grep: the file the whole building rests on
that no one currently employed has ever modified.

The method is Adam Tornhill's — behavioural code analysis, from *Your Code
as a Crime Scene* (2015) and *Software Design X-Rays* (2018). What is
implemented here is the cheap subset: change frequency and authorship
crossed with the import graph, plus temporal coupling — files that keep
changing in the same commit with no import between them.

Detectors take `(name, graph, history)`. When `history` is None — no
repository, a shallow clone, git unavailable — every Tier 3 detector
returns nothing. A missing history is not evidence of a young file.
"""

from __future__ import annotations

from archdogma.history import RepoHistory
from archdogma.probe.graph import ImportGraph
from archdogma.probe.tags.tier1 import Tag

# Defaults. As in Tiers 1 and 2, these are conventions, not findings.
DEFAULT_WALL_AFFERENT = 5
DEFAULT_WALL_STALE_DAYS = 730  # two years
DEFAULT_HOTSPOT_PERCENTILE = 0.9
DEFAULT_HOTSPOT_MIN_SLOC = 200
DEFAULT_HOTSPOT_MIN_COMMITS = 5
DEFAULT_BUS_FACTOR_AFFERENT = 5
DEFAULT_COUPLING_DEGREE = 0.6
DEFAULT_COUPLING_MIN_SHARED = 5
DEFAULT_COUPLING_MIN_REVISIONS = 5
DEFAULT_COUPLING_MAX_REPORTED = 3


def _years(days: int) -> str:
    if days >= 365:
        return f"{days / 365:.1f} years"
    return f"{days} days"


# ---------------------------------------------------------------------------
# load-bearing-wall
# ---------------------------------------------------------------------------
#
# High afferent coupling and no recent changes. The combination is the point:
#
#   - Stable and depended-upon is the ideal shape for a module. A mature
#     utility that stopped changing because it was finished is exactly this.
#   - Stable and depended-upon is also what fear looks like from the outside.
#     A module nobody touches because touching it breaks forty importers
#     produces identical numbers.
#
# The tag cannot tell those apart, and does not try. It says: this file
# carries load and has not moved in years — before you plan a refactor
# through it, find out which of the two it is.


def detect_load_bearing_wall(
    name: str,
    graph: ImportGraph,
    history: RepoHistory | None,
    afferent_threshold: int = DEFAULT_WALL_AFFERENT,
    stale_days: int = DEFAULT_WALL_STALE_DAYS,
) -> list[Tag]:
    """Flag a heavily depended-upon module that has not changed in years."""
    if history is None:
        return []
    node = graph.modules.get(name)
    if node is None:
        return []

    ca = graph.afferent(name)
    if ca < afferent_threshold:
        return []

    age = history.days_since_change(node.path)
    if age is None or age < stale_days:
        return []

    entry = history.for_path(node.path)
    commits = entry.commits if entry else 0
    return [
        Tag(
            name="load-bearing-wall",
            detail=(
                f"{ca} modules depend on this file, and it has not changed "
                f"in {_years(age)} ({commits} commits total). Either it was "
                f"finished, or it is the file everyone routes around. Find "
                f"out which before planning a refactor through it."
            ),
            line=1,
            col=0,
        )
    ]


# ---------------------------------------------------------------------------
# churn-hotspot
# ---------------------------------------------------------------------------
#
# Tornhill's central observation: complexity only costs you where the code
# actually changes. A gnarly file that nobody edits is a museum piece; a
# gnarly file edited every week is where the defects and the delivery drag
# accumulate. Rank by change frequency, filter by size, and the top of that
# list is where refactoring effort pays for itself.
#
# Size stands in for complexity here, which is crude. It is also the honest
# proxy available at this tier — the alternative would be inventing a
# composite score and presenting it as measurement.
#
# Churn is measured as a percentile within this repository, not an absolute
# commit count, because "23 commits" means different things in a two-month
# project and a ten-year one.


def detect_churn_hotspot(
    name: str,
    graph: ImportGraph,
    history: RepoHistory | None,
    percentile: float = DEFAULT_HOTSPOT_PERCENTILE,
    min_sloc: int = DEFAULT_HOTSPOT_MIN_SLOC,
    min_commits: int = DEFAULT_HOTSPOT_MIN_COMMITS,
) -> list[Tag]:
    """Flag a large module in the top churn percentile of its repository."""
    if history is None:
        return []
    node = graph.modules.get(name)
    if node is None or node.sloc < min_sloc:
        return []

    entry = history.for_path(node.path)
    if entry is None or entry.commits < min_commits:
        return []

    rank = history.churn_percentile(node.path)
    if rank is None or rank < percentile:
        return []

    return [
        Tag(
            name="churn-hotspot",
            detail=(
                f"{node.sloc} SLOC changed across {entry.commits} commits — "
                f"top {(1 - rank) * 100:.0f}% of this repository by change "
                f"frequency. Complexity costs most where the code moves; "
                f"this is where refactoring effort returns the most."
            ),
            line=1,
            col=0,
        )
    ]


# ---------------------------------------------------------------------------
# single-author-hub
# ---------------------------------------------------------------------------
#
# Bus factor, scoped to where it hurts. One author on a leaf script is
# unremarkable. One author on a module that forty others import means the
# system has a dependency on a person, and that dependency is not written
# down anywhere in the code.
#
# Author identity comes from `%aN` — git's mailmap-resolved name. A team
# that commits under inconsistent names will look more diverse than it is;
# a team using a shared bot account will look less.


def detect_single_author_hub(
    name: str,
    graph: ImportGraph,
    history: RepoHistory | None,
    afferent_threshold: int = DEFAULT_BUS_FACTOR_AFFERENT,
) -> list[Tag]:
    """Flag a heavily depended-upon module written by exactly one person."""
    if history is None:
        return []
    node = graph.modules.get(name)
    if node is None:
        return []

    ca = graph.afferent(name)
    if ca < afferent_threshold:
        return []

    entry = history.for_path(node.path)
    if entry is None or entry.author_count != 1:
        return []

    author = next(iter(entry.authors))
    return [
        Tag(
            name="single-author-hub",
            detail=(
                f"{ca} modules depend on this file and every one of its "
                f"{entry.commits} commits is by {author}. The knowledge to "
                f"change it safely exists in one place, and that place is "
                f"not the repository."
            ),
            line=1,
            col=0,
        )
    ]


# ---------------------------------------------------------------------------
# temporal-coupling
# ---------------------------------------------------------------------------
#
# Two modules that keep changing in the same commit while neither imports the
# other. The import graph says they are unrelated; four years of commits say
# otherwise, and the commits are the ones describing what maintenance actually
# costs.
#
# The import edge is subtracted on purpose. Files that change together *and*
# import each other are coupled in a way the structure already declares —
# that is a documented relationship, and reporting it would bury the signal
# in the obvious. What is left is the coupling nobody wrote down: a parser and
# the schema it assumes, a client and the server contract it mirrors, two
# implementations of a rule that was never extracted.
#
# Both filters exist because the naive version is famously noisy: without a
# sweep cap one formatter run couples the whole repository, and without a
# minimum revision count two files sharing their only commit score a perfect
# 1.0. See history.DEFAULT_MAX_FILES_PER_COMMIT for the first.


def detect_temporal_coupling(
    name: str,
    graph: ImportGraph,
    history: RepoHistory | None,
    degree: float = DEFAULT_COUPLING_DEGREE,
    min_shared: int = DEFAULT_COUPLING_MIN_SHARED,
    min_revisions: int = DEFAULT_COUPLING_MIN_REVISIONS,
    max_reported: int = DEFAULT_COUPLING_MAX_REPORTED,
) -> list[Tag]:
    """Flag modules that change together without importing each other."""
    if history is None:
        return []
    node = graph.modules.get(name)
    if node is None:
        return []

    own = history.for_path(node.path)
    if own is None or own.commits < min_revisions:
        return []

    found: list[tuple[str, float, int]] = []
    for other_path, shared in history.partners(own.path):
        if shared < min_shared:
            continue
        other_entry = history.files.get(other_path)
        if other_entry is None or other_entry.commits < min_revisions:
            continue
        deg = history.coupling_degree(own.path, other_path)
        if deg < degree:
            continue
        other_name = graph.name_for_path(history.root / other_path)
        if other_name is None or other_name == name:
            continue
        if graph.imports_either_way(name, other_name):
            continue
        found.append((other_name, deg, shared))

    if not found:
        return []

    found.sort(key=lambda item: (-item[1], -item[2], item[0]))
    shown = found[:max_reported]
    listed = ", ".join(f"{n} ({d:.0%}, {s} commits)" for n, d, s in shown)
    if len(found) > max_reported:
        listed += f", +{len(found) - max_reported} more"

    return [
        Tag(
            name="temporal-coupling",
            detail=(
                f"Changes together with {listed} — and there is no import "
                f"between them. The structure says these files are unrelated; "
                f"the commit history says maintaining one means maintaining "
                f"the other."
            ),
            line=1,
            col=0,
        )
    ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
#
# Signature differs from Tier 2 by one argument: (name, graph, history).
# Kept as a separate registry rather than widening the Tier 2 protocol,
# because Tier 3 is the tier that can be switched off — no repository, no
# history, no tags — and that ought to be visible in the type, not hidden
# in a None check inside a shared loop.

TIER3_DETECTORS: tuple[tuple[str, "object"], ...] = (
    ("load-bearing-wall", detect_load_bearing_wall),
    ("churn-hotspot", detect_churn_hotspot),
    ("single-author-hub", detect_single_author_hub),
    ("temporal-coupling", detect_temporal_coupling),
)
