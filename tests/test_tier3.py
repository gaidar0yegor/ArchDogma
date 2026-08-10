"""Unit tests for the Tier 3 detectors — structure crossed with history."""

from __future__ import annotations

from pathlib import Path

from archdogma.history import FileHistory, RepoHistory, _index_partners, _pair
from archdogma.probe.tags.tier3 import (
    TIER3_DETECTORS,
    detect_churn_hotspot,
    detect_load_bearing_wall,
    detect_single_author_hub,
    detect_temporal_coupling,
)

from tests.test_tier2 import fan_in, graph_from_edges, tag_names

NOW = 1704067200  # 2024-01-01, the reference instant for every age here
DAY = 86400


def _path_of(module: str) -> str:
    return f"{module.replace('.', '/')}.py"


def history(
    entries: dict[str, tuple[int, int, tuple[str, ...]]],
    as_of: int = NOW,
    co_changes: dict[tuple[str, str], int] | None = None,
) -> RepoHistory:
    """Build a RepoHistory from {module: (commits, days_ago, authors)}.

    Paths mirror what `graph_from_edges` produces, so the two fixtures line
    up without either knowing about the other. `co_changes` is keyed by
    module name pairs and translated to paths here.
    """
    files = {}
    for module, (commits, days_ago, authors) in entries.items():
        path = _path_of(module)
        last = as_of - days_ago * DAY
        files[path] = FileHistory(
            path=path,
            commits=commits,
            first_commit=last - 30 * DAY,
            last_commit=last,
            authors=frozenset(authors),
        )
    pairs = {
        _pair(_path_of(a), _path_of(b)): n
        for (a, b), n in (co_changes or {}).items()
    }
    return RepoHistory(
        root=Path("/repo"),
        as_of=as_of,
        files=files,
        co_changes=pairs,
        partner_index=_index_partners(pairs),
    )


def quiet_history(modules: list[str], commits: int = 1) -> RepoHistory:
    """Every module changed yesterday by two people — a neutral background."""
    return history({m: (commits, 1, ("Ada", "Bob")) for m in modules})


# ---------------------------------------------------------------------------
# Registry and the no-history contract
# ---------------------------------------------------------------------------


def test_all_detectors_registered() -> None:
    assert [name for name, _ in TIER3_DETECTORS] == [
        "load-bearing-wall",
        "churn-hotspot",
        "single-author-hub",
        "temporal-coupling",
    ]


def test_every_detector_is_silent_without_history() -> None:
    """No repository must never be reported as a clean repository."""
    graph = graph_from_edges(fan_in("core", 20), sloc={"core": 5000})
    for _name, detector in TIER3_DETECTORS:
        assert detector("core", graph, None) == []


def test_detectors_are_silent_for_files_missing_from_history() -> None:
    """A file git has never seen — new, or ignored — is not evidence."""
    graph = graph_from_edges(fan_in("core", 20))
    hist = history({"something.else": (5, 5, ("Ada",))})
    for _name, detector in TIER3_DETECTORS:
        assert detector("core", graph, hist) == []


# ---------------------------------------------------------------------------
# load-bearing-wall
# ---------------------------------------------------------------------------


def test_old_and_depended_upon_flags() -> None:
    graph = graph_from_edges(fan_in("core", 8))
    hist = history({"core": (3, 1200, ("Ada", "Bob"))})
    assert tag_names(detect_load_bearing_wall("core", graph, hist)) == [
        "load-bearing-wall"
    ]


def test_old_but_barely_used_does_not_flag() -> None:
    graph = graph_from_edges(fan_in("core", 2))
    hist = history({"core": (3, 1200, ("Ada",))})
    assert detect_load_bearing_wall("core", graph, hist) == []


def test_depended_upon_but_recently_changed_does_not_flag() -> None:
    graph = graph_from_edges(fan_in("core", 20))
    hist = history({"core": (3, 10, ("Ada",))})
    assert detect_load_bearing_wall("core", graph, hist) == []


def test_wall_thresholds_are_configurable() -> None:
    graph = graph_from_edges(fan_in("core", 3))
    hist = history({"core": (2, 400, ("Ada",))})
    assert detect_load_bearing_wall("core", graph, hist) == []
    assert (
        detect_load_bearing_wall(
            "core", graph, hist, afferent_threshold=3, stale_days=365
        )
        != []
    )


def test_wall_detail_reports_dependents_and_age_in_years() -> None:
    graph = graph_from_edges(fan_in("core", 9))
    hist = history({"core": (4, 1095, ("Ada",))})
    detail = detect_load_bearing_wall("core", graph, hist)[0].detail
    assert "9 modules depend" in detail
    assert "3.0 years" in detail


def test_wall_detail_states_the_ambiguity() -> None:
    """The tag must not claim to know whether the file is finished or feared."""
    graph = graph_from_edges(fan_in("core", 9))
    hist = history({"core": (4, 1095, ("Ada",))})
    detail = detect_load_bearing_wall("core", graph, hist)[0].detail
    assert "Either it was finished" in detail


# ---------------------------------------------------------------------------
# churn-hotspot
# ---------------------------------------------------------------------------


def _hotspot_setup() -> tuple:
    modules = [f"m{i}" for i in range(10)]
    graph = graph_from_edges({m: () for m in modules}, sloc={"m0": 800})
    entries = {m: (1, 5, ("Ada", "Bob")) for m in modules}
    entries["m0"] = (40, 5, ("Ada", "Bob"))
    return graph, history(entries)


def test_large_and_high_churn_flags() -> None:
    graph, hist = _hotspot_setup()
    assert tag_names(detect_churn_hotspot("m0", graph, hist)) == ["churn-hotspot"]


def test_high_churn_but_small_does_not_flag() -> None:
    modules = [f"m{i}" for i in range(10)]
    graph = graph_from_edges({m: () for m in modules}, sloc={"m0": 40})
    entries = {m: (1, 5, ("Ada",)) for m in modules}
    entries["m0"] = (40, 5, ("Ada",))
    assert detect_churn_hotspot("m0", graph, history(entries)) == []


def test_large_but_quiet_does_not_flag() -> None:
    modules = [f"m{i}" for i in range(10)]
    graph = graph_from_edges({m: () for m in modules}, sloc={"m0": 900})
    entries = {m: (30, 5, ("Ada",)) for m in modules}
    entries["m0"] = (1, 5, ("Ada",))
    assert detect_churn_hotspot("m0", graph, history(entries)) == []


def test_min_commits_floor_suppresses_tiny_repositories() -> None:
    """In a repo where everything has one commit, nothing is a hotspot."""
    modules = [f"m{i}" for i in range(5)]
    graph = graph_from_edges({m: () for m in modules}, sloc={"m0": 900})
    hist = history({m: (1, 5, ("Ada",)) for m in modules})
    assert detect_churn_hotspot("m0", graph, hist) == []


def test_hotspot_percentile_is_configurable() -> None:
    graph, hist = _hotspot_setup()
    assert detect_churn_hotspot("m0", graph, hist, percentile=1.01) == []


def test_hotspot_detail_reports_size_and_commit_count() -> None:
    graph, hist = _hotspot_setup()
    detail = detect_churn_hotspot("m0", graph, hist)[0].detail
    assert "800 SLOC" in detail
    assert "40 commits" in detail


# ---------------------------------------------------------------------------
# single-author-hub
# ---------------------------------------------------------------------------


def test_sole_author_of_a_hub_flags() -> None:
    graph = graph_from_edges(fan_in("core", 7))
    hist = history({"core": (12, 5, ("Ada",))})
    tags = detect_single_author_hub("core", graph, hist)
    assert tag_names(tags) == ["single-author-hub"]
    assert "Ada" in tags[0].detail


def test_two_authors_does_not_flag() -> None:
    graph = graph_from_edges(fan_in("core", 7))
    hist = history({"core": (12, 5, ("Ada", "Bob"))})
    assert detect_single_author_hub("core", graph, hist) == []


def test_sole_author_of_a_leaf_does_not_flag() -> None:
    """One author on a module nobody imports is not a system risk."""
    graph = graph_from_edges(fan_in("core", 2))
    hist = history({"core": (12, 5, ("Ada",))})
    assert detect_single_author_hub("core", graph, hist) == []


def test_bus_factor_threshold_is_configurable() -> None:
    graph = graph_from_edges(fan_in("core", 3))
    hist = history({"core": (12, 5, ("Ada",))})
    assert detect_single_author_hub("core", graph, hist) == []
    assert detect_single_author_hub("core", graph, hist, afferent_threshold=3) != []


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------


def test_a_module_can_be_wall_and_single_author_at_once() -> None:
    graph = graph_from_edges(fan_in("core", 12))
    hist = history({"core": (4, 1500, ("Ada",))})
    fired = []
    for _name, detector in TIER3_DETECTORS:
        fired.extend(tag_names(detector("core", graph, hist)))
    assert set(fired) == {"load-bearing-wall", "single-author-hub"}


# ---------------------------------------------------------------------------
# temporal-coupling
# ---------------------------------------------------------------------------


def _coupled(edges=None, shared=8, commits=10):
    """Two modules changing together, with edges under the caller's control."""
    graph = graph_from_edges(edges if edges is not None else {"a": (), "b": ()})
    hist = history(
        {"a": (commits, 5, ("Ada",)), "b": (commits, 5, ("Ada",))},
        co_changes={("a", "b"): shared},
    )
    return graph, hist


def test_co_changing_unrelated_modules_flag() -> None:
    graph, hist = _coupled()
    tags = detect_temporal_coupling("a", graph, hist)
    assert tag_names(tags) == ["temporal-coupling"]
    assert "b" in tags[0].detail


def test_both_ends_of_the_pair_are_flagged() -> None:
    graph, hist = _coupled()
    assert detect_temporal_coupling("b", graph, hist) != []


def test_import_edge_suppresses_the_tag() -> None:
    """Coupling the structure already declares is not a hidden relationship."""
    graph, hist = _coupled(edges={"a": ("b",), "b": ()})
    assert detect_temporal_coupling("a", graph, hist) == []
    assert detect_temporal_coupling("b", graph, hist) == []


def test_reverse_import_edge_also_suppresses() -> None:
    graph, hist = _coupled(edges={"a": (), "b": ("a",)})
    assert detect_temporal_coupling("a", graph, hist) == []


def test_low_degree_does_not_flag() -> None:
    graph, hist = _coupled(shared=3, commits=20)
    assert detect_temporal_coupling("a", graph, hist) == []


def test_few_shared_commits_does_not_flag() -> None:
    """A perfect degree over two commits is not evidence of anything."""
    graph, hist = _coupled(shared=2, commits=2)
    assert detect_temporal_coupling("a", graph, hist) == []


def test_min_revisions_floor_suppresses_young_files() -> None:
    graph, hist = _coupled(shared=4, commits=4)
    assert detect_temporal_coupling("a", graph, hist) == []


def test_no_co_changes_no_tag() -> None:
    graph = graph_from_edges({"a": (), "b": ()})
    hist = history({"a": (10, 5, ("Ada",)), "b": (10, 5, ("Ada",))})
    assert detect_temporal_coupling("a", graph, hist) == []


def test_partner_outside_the_graph_is_ignored() -> None:
    """A co-changing file that was not scanned cannot be named as a module."""
    graph = graph_from_edges({"a": ()})
    hist = history(
        {"a": (10, 5, ("Ada",)), "b": (10, 5, ("Ada",))},
        co_changes={("a", "b"): 8},
    )
    assert detect_temporal_coupling("a", graph, hist) == []


def test_thresholds_are_configurable() -> None:
    graph, hist = _coupled(shared=3, commits=20)
    assert detect_temporal_coupling("a", graph, hist) == []
    assert (
        detect_temporal_coupling("a", graph, hist, degree=0.1, min_shared=3) != []
    )


def test_partners_are_capped_and_the_remainder_counted() -> None:
    names = ["a", *[f"p{i}" for i in range(5)]]
    graph = graph_from_edges({n: () for n in names})
    hist = history(
        {n: (10, 5, ("Ada",)) for n in names},
        co_changes={("a", f"p{i}"): 8 for i in range(5)},
    )
    detail = detect_temporal_coupling("a", graph, hist)[0].detail
    assert "+2 more" in detail


def test_detail_reports_degree_and_shared_count() -> None:
    graph, hist = _coupled(shared=8, commits=10)
    detail = detect_temporal_coupling("a", graph, hist)[0].detail
    assert "80%" in detail
    assert "8 commits" in detail
