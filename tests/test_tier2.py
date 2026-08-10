"""Unit tests for the Tier 2 module-level detectors.

Graphs are built directly from an edge map rather than from files, so a
threshold test says exactly what it means: this many dependents, this much
code, this instability. File-level wiring is covered in test_module_scan.py.
"""

from __future__ import annotations

from pathlib import Path

from archdogma.probe.graph import ImportGraph, ModuleNode, find_cycles
from archdogma.probe.tags.tier2 import (
    TIER2_DETECTORS,
    detect_circular_import,
    detect_god_module,
    detect_hub_module,
    detect_unstable_dependency,
)


def graph_from_edges(
    edges: dict[str, tuple[str, ...]],
    sloc: dict[str, int] | None = None,
    defs: dict[str, int] | None = None,
) -> ImportGraph:
    """Build an ImportGraph from an edge map, with optional size overrides."""
    sloc = sloc or {}
    defs = defs or {}
    names = set(edges) | {t for targets in edges.values() for t in targets}
    modules = {
        name: ModuleNode(
            name=name,
            path=Path(f"{name.replace('.', '/')}.py"),
            sloc=sloc.get(name, 10),
            def_count=defs.get(name, 1),
        )
        for name in names
    }
    full_edges = {name: edges.get(name, ()) for name in names}
    reverse: dict[str, list[str]] = {name: [] for name in names}
    for importer, targets in full_edges.items():
        for target in targets:
            reverse[target].append(importer)
    return ImportGraph(
        modules=modules,
        edges=full_edges,
        reverse={k: tuple(sorted(v)) for k, v in reverse.items()},
        external={k: () for k in names},
        cycles=find_cycles(full_edges),
    )


def fan_in(target: str, count: int) -> dict[str, tuple[str, ...]]:
    """`count` distinct modules all importing `target`."""
    return {f"dep{i}": (target,) for i in range(count)}


def tag_names(tags: list) -> list[str]:
    return [t.name for t in tags]


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------


def test_all_four_detectors_registered() -> None:
    names = [name for name, _ in TIER2_DETECTORS]
    assert names == [
        "circular-import",
        "hub-module",
        "god-module",
        "unstable-dependency",
    ]


def test_registry_callables_accept_name_and_graph() -> None:
    graph = graph_from_edges({"a": ()})
    for _name, detector in TIER2_DETECTORS:
        assert detector("a", graph) == []


# ---------------------------------------------------------------------------
# circular-import
# ---------------------------------------------------------------------------


def test_no_cycle_no_flag() -> None:
    graph = graph_from_edges({"a": ("b",), "b": ()})
    assert detect_circular_import("a", graph) == []


def test_two_module_cycle_flags_both() -> None:
    graph = graph_from_edges({"a": ("b",), "b": ("a",)})
    assert tag_names(detect_circular_import("a", graph)) == ["circular-import"]
    assert tag_names(detect_circular_import("b", graph)) == ["circular-import"]


def test_cycle_detail_names_the_other_members() -> None:
    graph = graph_from_edges({"a": ("b",), "b": ("c",), "c": ("a",)})
    detail = detect_circular_import("a", graph)[0].detail
    assert "b" in detail and "c" in detail
    assert "3 modules" in detail


def test_cycle_detail_truncates_large_cycles() -> None:
    members = [f"m{i}" for i in range(8)]
    edges = {m: (members[(i + 1) % 8],) for i, m in enumerate(members)}
    detail = detect_circular_import("m0", graph_from_edges(edges))[0].detail
    assert "+3 more" in detail


def test_module_outside_the_cycle_is_not_flagged() -> None:
    graph = graph_from_edges({"a": ("b",), "b": ("a",), "outside": ("a",)})
    assert detect_circular_import("outside", graph) == []


def test_cycle_points_at_the_offending_import_line(tmp_path: Path) -> None:
    """The line number must come from the import, not default to 1."""
    from archdogma.probe.graph import build_graph

    from tests.test_graph import write_pkg

    paths = write_pkg(
        tmp_path,
        {
            "app/a.py": "import os\n\nfrom app import b\n",
            "app/b.py": "from app import a\n",
        },
    )
    graph = build_graph(paths)
    tag = detect_circular_import("app.a", graph)[0]
    assert tag.line == 3


# ---------------------------------------------------------------------------
# hub-module
# ---------------------------------------------------------------------------


def test_hub_below_threshold_no_flag() -> None:
    graph = graph_from_edges(fan_in("core", 9))
    assert detect_hub_module("core", graph) == []


def test_hub_at_threshold_flags() -> None:
    graph = graph_from_edges(fan_in("core", 10))
    assert tag_names(detect_hub_module("core", graph)) == ["hub-module"]


def test_hub_threshold_is_configurable() -> None:
    graph = graph_from_edges(fan_in("core", 4))
    assert detect_hub_module("core", graph, threshold=3) != []
    assert detect_hub_module("core", graph, threshold=5) == []


def test_hub_detail_reports_dependent_count_and_share() -> None:
    graph = graph_from_edges(fan_in("core", 12))
    detail = detect_hub_module("core", graph)[0].detail
    assert "12 modules import this one" in detail
    assert "%" in detail


def test_hub_ignores_outgoing_edges() -> None:
    """Efferent coupling must not stand in for afferent coupling."""
    graph = graph_from_edges({"greedy": tuple(f"m{i}" for i in range(20))})
    assert detect_hub_module("greedy", graph) == []


# ---------------------------------------------------------------------------
# god-module
# ---------------------------------------------------------------------------


def test_god_module_needs_both_signals() -> None:
    big_only = graph_from_edges({"m": ()}, sloc={"m": 900}, defs={"m": 3})
    wide_only = graph_from_edges({"m": ()}, sloc={"m": 100}, defs={"m": 40})
    assert detect_god_module("m", big_only) == []
    assert detect_god_module("m", wide_only) == []


def test_god_module_flags_when_both_cross() -> None:
    graph = graph_from_edges({"m": ()}, sloc={"m": 700}, defs={"m": 25})
    assert tag_names(detect_god_module("m", graph)) == ["god-module"]


def test_god_module_at_exact_thresholds_flags() -> None:
    graph = graph_from_edges({"m": ()}, sloc={"m": 600}, defs={"m": 20})
    assert detect_god_module("m", graph) != []


def test_god_module_thresholds_are_configurable() -> None:
    graph = graph_from_edges({"m": ()}, sloc={"m": 200}, defs={"m": 5})
    assert detect_god_module("m", graph, sloc_threshold=100, def_threshold=4) != []


def test_god_module_detail_reports_both_numbers() -> None:
    graph = graph_from_edges({"m": ()}, sloc={"m": 700}, defs={"m": 25})
    detail = detect_god_module("m", graph)[0].detail
    assert "700 SLOC" in detail
    assert "25 top-level" in detail


def test_god_module_unknown_name_is_silent() -> None:
    graph = graph_from_edges({"m": ()})
    assert detect_god_module("does-not-exist", graph) == []


# ---------------------------------------------------------------------------
# unstable-dependency
# ---------------------------------------------------------------------------


def test_stable_module_importing_unstable_one_flags() -> None:
    # core: Ca=4, Ce=1 → I=0.2 (stable). volatile: Ca=1, Ce=3 → I=0.75.
    edges = {
        **fan_in("core", 4),
        "core": ("volatile",),
        "volatile": ("x", "y", "z"),
    }
    tags = detect_unstable_dependency("core", graph_from_edges(edges))
    assert tag_names(tags) == ["unstable-dependency"]
    assert "volatile" in tags[0].detail


def test_unstable_module_is_not_judged() -> None:
    """The principle constrains stable modules; unstable ones may depend up."""
    edges = {"leaf": ("a", "b", "c"), "a": (), "b": (), "c": ()}
    assert detect_unstable_dependency("leaf", graph_from_edges(edges)) == []


def test_small_degree_module_is_skipped() -> None:
    """I is meaningless at one edge — do not report on it."""
    edges = {"core": ("volatile",), "volatile": ("x", "y", "z")}
    assert detect_unstable_dependency("core", graph_from_edges(edges)) == []


def test_low_gap_dependency_is_not_flagged() -> None:
    edges = {**fan_in("core", 4), "core": ("near",), **fan_in("near", 3)}
    edges["near"] = ("q",)
    assert detect_unstable_dependency("core", graph_from_edges(edges)) == []


def test_multiple_violations_produce_multiple_tags() -> None:
    edges = {
        **fan_in("core", 5),
        "core": ("v1", "v2"),
        "v1": ("x", "y", "z"),
        "v2": ("x", "y", "z"),
    }
    tags = detect_unstable_dependency("core", graph_from_edges(edges))
    assert len(tags) == 2
    assert {t.name for t in tags} == {"unstable-dependency"}


def test_unstable_dependency_thresholds_are_configurable() -> None:
    edges = {**fan_in("core", 4), "core": ("volatile",), "volatile": ("x", "y", "z")}
    graph = graph_from_edges(edges)
    assert detect_unstable_dependency("core", graph, gap=0.9) == []
    assert detect_unstable_dependency("core", graph, stable_ceiling=0.0) == []


def test_unstable_dependency_detail_reports_both_instabilities() -> None:
    edges = {**fan_in("core", 4), "core": ("volatile",), "volatile": ("x", "y", "z")}
    detail = detect_unstable_dependency("core", graph_from_edges(edges))[0].detail
    assert "I=0.20" in detail
    assert "I=0.75" in detail
