"""Integration tests for `scan_modules` — graph, detectors and catalog wiring."""

from __future__ import annotations

from pathlib import Path

from archdogma.catalog.loader import load_catalog
from archdogma.probe.scanner import scan_modules

from tests.test_graph import write_pkg


def _big_module(defs: int, body_lines: int) -> str:
    """A module large enough to trip god-module thresholds."""
    chunks = []
    for i in range(defs):
        body = "\n".join(f"    x{j} = {j}" for j in range(body_lines))
        chunks.append(f"def f{i}():\n{body}\n")
    return "\n".join(chunks)


def test_scan_reports_every_module(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    result = scan_modules(tmp_path)
    assert {m.name for m in result.modules} == {"app", "app.a", "app.b"}


def test_metrics_travel_with_unflagged_modules(tmp_path: Path) -> None:
    """A module below every threshold still reports its coupling numbers."""
    write_pkg(tmp_path, {"app/core.py": "", "app/a.py": "from app import core\n"})
    result = scan_modules(tmp_path)
    core = next(m for m in result.modules if m.name == "app.core")
    assert core.tags == ()
    assert core.afferent == 1
    assert core.instability == 0.0


def test_clean_project_produces_no_tags(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    assert scan_modules(tmp_path).tag_count == 0


def test_cycle_is_reported_for_both_modules(tmp_path: Path) -> None:
    write_pkg(
        tmp_path,
        {"app/a.py": "from app import b\n", "app/b.py": "from app import a\n"},
    )
    result = scan_modules(tmp_path)
    flagged = {m.name for m in result.flagged}
    assert {"app.a", "app.b"} <= flagged
    assert result.tag_count >= 2


def test_god_module_reported_end_to_end(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/fat.py": _big_module(defs=25, body_lines=30)})
    result = scan_modules(tmp_path)
    fat = next(m for m in result.modules if m.name == "app.fat")
    assert "god-module" in {t.name for t in fat.tags}


def test_modules_are_returned_in_stable_order(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/z.py": "", "app/a.py": "", "app/m.py": ""})
    names = [m.name for m in scan_modules(tmp_path).modules]
    assert names == sorted(names)


def test_excludes_are_honoured(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/tests/test_a.py": ""})
    result = scan_modules(tmp_path, excludes=("app/tests/*",))
    assert not any("test_a" in m.name for m in result.modules)


def test_syntax_error_does_not_abort_the_scan(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/ok.py": "", "app/broken.py": "def f(\n"})
    result = scan_modules(tmp_path)
    assert any(m.name == "app.ok" for m in result.modules)
    assert result.graph.parse_errors


def test_graph_is_exposed_on_the_result(tmp_path: Path) -> None:
    """Agents need the structure, not just the findings."""
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    graph = scan_modules(tmp_path).graph
    assert graph.edges["app.b"] == ("app.a",)
    assert graph.reverse["app.a"] == ("app.b",)


def test_scanning_archdogma_itself_finds_its_own_god_module() -> None:
    """Dogfooding: tier1.py is over both god-module thresholds."""
    result = scan_modules(Path("src"))
    tier1 = next(
        m for m in result.modules if m.name == "archdogma.probe.tags.tier1"
    )
    assert "god-module" in {t.name for t in tier1.tags}


def test_catalog_links_resolve_for_module_tags(tmp_path: Path) -> None:
    """A Tier 2 tag must reach the catalog through the same tag_index."""
    catalog = load_catalog(Path("catalog/dogmas.yaml"))
    write_pkg(
        tmp_path,
        {"app/a.py": "from app import b\n", "app/b.py": "from app import a\n"},
    )
    result = scan_modules(tmp_path, catalog=catalog)
    flagged = next(m for m in result.flagged if m.name == "app.a")
    linked_tags = {link.tag_name for link in flagged.catalog_links}
    assert "circular-import" in linked_tags


def test_history_is_absent_outside_a_git_repo(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": ""})
    result = scan_modules(tmp_path)
    assert result.history is None
    assert all(m.commits is None for m in result.modules)


def test_history_metrics_travel_with_results_in_a_repo() -> None:
    """Scanning ArchDogma itself must attach real commit counts."""
    result = scan_modules(Path("src"))
    assert result.history is not None
    tier1 = next(m for m in result.modules if m.name == "archdogma.probe.tags.tier1")
    assert tier1.commits is not None and tier1.commits > 0
    assert tier1.author_count is not None and tier1.author_count >= 1


def test_use_history_false_disables_tier3() -> None:
    result = scan_modules(Path("src"), use_history=False)
    assert result.history is None
    tier3 = {"load-bearing-wall", "churn-hotspot", "single-author-hub"}
    fired = {t.name for m in result.modules for t in m.tags}
    assert not (fired & tier3)


def test_tier3_catalog_links_resolve() -> None:
    """Every Tier 3 tag name must exist in the catalog's tag index."""
    catalog = load_catalog(Path("catalog/dogmas.yaml"))
    for tag in ("load-bearing-wall", "churn-hotspot", "single-author-hub"):
        assert tag in catalog.tag_index, f"{tag} is not linked to any catalog entry"


def test_tier2_catalog_links_resolve() -> None:
    catalog = load_catalog(Path("catalog/dogmas.yaml"))
    for tag in (
        "circular-import",
        "hub-module",
        "god-module",
        "unstable-dependency",
    ):
        assert tag in catalog.tag_index, f"{tag} is not linked to any catalog entry"


def test_no_catalog_means_no_links(tmp_path: Path) -> None:
    write_pkg(
        tmp_path,
        {"app/a.py": "from app import b\n", "app/b.py": "from app import a\n"},
    )
    result = scan_modules(tmp_path, catalog=None)
    assert all(m.catalog_links == () for m in result.modules)
