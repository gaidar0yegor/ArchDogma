"""Tests for the `modules` command and the machine-readable report payload.

The payload assertions are the point of this file. `scan --format json`
shipped tag names with no catalog context, which made the agent-facing
output indistinguishable from any linter's. These tests pin the fix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from archdogma.catalog.loader import load_catalog
from archdogma.cli import main
from archdogma.report import catalog_payload, history_payload, tags_payload

from tests.test_graph import write_pkg

CATALOG = str(Path("catalog/dogmas.yaml"))


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cyclic_project(tmp_path: Path) -> Path:
    write_pkg(
        tmp_path,
        {
            "app/a.py": "from app import b\n",
            "app/b.py": "from app import a\n",
        },
    )
    return tmp_path


def run_json(runner: CliRunner, *args: str) -> dict:
    """Invoke a command and parse stdout only.

    Reading `result.stdout` rather than `result.output` is deliberate: any
    diagnostic that leaks into stdout breaks every consumer piping this into
    a parser, and a helper that merges the streams would hide exactly that.
    """
    result = runner.invoke(main, [*args, "--format", "json", "--no-fail"])
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# modules — plain output
# ---------------------------------------------------------------------------


def test_clean_project_reports_no_tags(runner: CliRunner, tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    result = runner.invoke(main, ["modules", str(tmp_path)])
    assert result.exit_code == 0
    assert "0 tag(s)" in result.output


def test_cycle_is_reported_in_plain_output(
    runner: CliRunner, cyclic_project: Path
) -> None:
    result = runner.invoke(main, ["modules", str(cyclic_project), "--no-fail"])
    assert "circular-import" in result.output
    assert "1 cycle(s)" in result.output


def test_fail_flag_exits_non_zero_on_tags(
    runner: CliRunner, cyclic_project: Path
) -> None:
    result = runner.invoke(main, ["modules", str(cyclic_project), "--fail"])
    assert result.exit_code == 1


def test_no_fail_flag_exits_zero_on_tags(
    runner: CliRunner, cyclic_project: Path
) -> None:
    result = runner.invoke(main, ["modules", str(cyclic_project), "--no-fail"])
    assert result.exit_code == 0


def test_flagged_only_is_the_default(runner: CliRunner, tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    result = runner.invoke(main, ["modules", str(tmp_path)])
    assert "app.a" not in result.output.split("\n\n")[0]


def test_all_flag_lists_every_module(runner: CliRunner, tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    result = runner.invoke(main, ["modules", str(tmp_path), "--all"])
    assert "app.a" in result.output
    assert "app.b" in result.output


def test_missing_history_is_announced_not_silent(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Absence of Tier 3 must never read as a clean Tier 3."""
    write_pkg(tmp_path, {"app/a.py": ""})
    result = runner.invoke(main, ["modules", str(tmp_path)])
    assert "Tier 3 skipped" in result.output


def test_empty_directory_says_so(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, ["modules", str(tmp_path)])
    assert "No Python files found." in result.output


# ---------------------------------------------------------------------------
# modules — JSON output
# ---------------------------------------------------------------------------


def test_json_reports_graph_shape(runner: CliRunner, cyclic_project: Path) -> None:
    data = run_json(runner, "modules", str(cyclic_project))
    assert data["cycles"] == [["app.a", "app.b"]]
    assert data["total_modules"] >= 2
    assert data["total_edges"] == 2


def test_json_carries_coupling_metrics(runner: CliRunner, tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    data = run_json(runner, "modules", str(tmp_path), "--all")
    a = next(m for m in data["modules"] if m["name"] == "app.a")
    assert a["afferent"] == 1
    assert a["efferent"] == 0
    assert a["instability"] == 0.0


def test_json_history_block_states_unavailability(
    runner: CliRunner, tmp_path: Path
) -> None:
    write_pkg(tmp_path, {"app/a.py": ""})
    data = run_json(runner, "modules", str(tmp_path))
    assert data["history"]["available"] is False
    assert "not evidence" in data["history"]["reason"]


def test_json_history_block_present_in_a_repo(runner: CliRunner) -> None:
    data = run_json(runner, "modules", "src")
    if not data["history"]["available"]:
        pytest.skip("no git history here (tarball or shallow clone)")
    assert data["history"]["follows_renames"] is False
    assert data["history"]["files_with_history"] > 0


def test_json_reports_parse_errors(runner: CliRunner, tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/ok.py": "", "app/bad.py": "def f(\n"})
    data = run_json(runner, "modules", str(tmp_path))
    assert data["parse_errors"]


# ---------------------------------------------------------------------------
# Catalog context in JSON — the gap this closes
# ---------------------------------------------------------------------------


def test_module_tags_reference_catalog_entries(
    runner: CliRunner, cyclic_project: Path
) -> None:
    data = run_json(runner, "modules", str(cyclic_project), "--catalog", CATALOG)
    tags = [t for m in data["modules"] for t in m["tags"]]
    circular = next(t for t in tags if t["name"] == "circular-import")
    assert "clean-architecture" in circular["dogmas"]


def test_referenced_entries_are_emitted_once_at_top_level(
    runner: CliRunner, cyclic_project: Path
) -> None:
    data = run_json(runner, "modules", str(cyclic_project), "--catalog", CATALOG)
    entries = data["catalog"]["entries"]
    assert "clean-architecture" in entries
    assert entries["clean-architecture"]["break_when"]
    assert entries["clean-architecture"]["main_signal"]


def test_unreferenced_entries_are_not_emitted(
    runner: CliRunner, cyclic_project: Path
) -> None:
    """The payload carries the dogmas in play, not the whole catalog."""
    data = run_json(runner, "modules", str(cyclic_project), "--catalog", CATALOG)
    entries = data["catalog"]["entries"]
    assert "hundred-percent-coverage" not in entries
    assert len(entries) < 5


def test_scan_json_now_carries_dogma_ids(runner: CliRunner, tmp_path: Path) -> None:
    """The regression this closes: scan JSON used to drop catalog links."""
    src = tmp_path / "m.py"
    src.write_text(
        "def f(a, b, c, d, e, g, h):\n    return a\n",
        encoding="utf-8",
    )
    data = run_json(runner, "scan", str(src), "--catalog", CATALOG)
    tags = [t for f in data["files"] for i in f.get("items", []) for t in i["tags"]]
    params = next(t for t in tags if t["name"] == "too-many-params")
    assert params["dogmas"] == ["long-parameter-list"]
    assert "long-parameter-list" in data["catalog"]["entries"]


def test_json_says_so_when_no_catalog_was_found(
    runner: CliRunner, cyclic_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(cyclic_project)
    data = run_json(runner, "modules", str(cyclic_project))
    assert data["catalog"]["loaded"] is False
    assert "linter report" in data["catalog"]["note"]


@pytest.mark.parametrize("command", ["modules", "scan"])
def test_diagnostics_never_contaminate_json_stdout(
    runner: CliRunner,
    cyclic_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
) -> None:
    """stdout must stay parseable even when the catalog is missing.

    The "no catalog found" note is useful and must keep being printed — to
    stderr. On stdout it would break every consumer that pipes this into a
    parser, which is the entire audience for --format json.
    """
    monkeypatch.chdir(cyclic_project)
    result = runner.invoke(
        main, [command, str(cyclic_project), "--format", "json", "--no-fail"]
    )
    assert result.exit_code == 0
    json.loads(result.stdout)  # raises if anything else was written
    assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# report helpers, in isolation
# ---------------------------------------------------------------------------


def test_tags_payload_groups_ids_by_tag_name() -> None:
    from archdogma.probe.tags.tier1 import Tag
    from archdogma.probe.walker import CatalogLink

    tags = (Tag(name="hub-module", detail="d", line=1, col=0),)
    links = (
        CatalogLink(
            tag_name="hub-module",
            entry_id="dry",
            entry_kind="dogma",
            entry_title="DRY",
            entry_number=3,
        ),
    )
    payload = tags_payload(tags, links)
    assert payload[0]["dogmas"] == ["dry"]


def test_tags_payload_deduplicates_repeated_links() -> None:
    from archdogma.probe.tags.tier1 import Tag
    from archdogma.probe.walker import CatalogLink

    tags = (Tag(name="hub-module", detail="d", line=1, col=0),)
    link = CatalogLink(
        tag_name="hub-module",
        entry_id="dry",
        entry_kind="dogma",
        entry_title="DRY",
        entry_number=3,
    )
    assert tags_payload(tags, (link, link))[0]["dogmas"] == ["dry"]


def test_tags_payload_tolerates_missing_links() -> None:
    from archdogma.probe.tags.tier1 import Tag

    payload = tags_payload((Tag(name="x", detail="d", line=1, col=0),), ())
    assert payload[0]["dogmas"] == []


def test_catalog_payload_without_catalog_flags_itself() -> None:
    out = catalog_payload({"modules": []}, None)
    assert out["loaded"] is False
    assert out["entries"] == {}


def test_catalog_payload_collects_ids_from_nested_structures() -> None:
    catalog = load_catalog(Path(CATALOG))
    payload = {"a": [{"tags": [{"dogmas": ["dry", "solid"]}]}]}
    entries = catalog_payload(payload, catalog)["entries"]
    assert set(entries) == {"dry", "solid"}


def test_catalog_payload_ignores_unknown_ids() -> None:
    catalog = load_catalog(Path(CATALOG))
    entries = catalog_payload({"dogmas": ["not-a-real-id"]}, catalog)["entries"]
    assert entries == {}


def test_history_payload_without_history() -> None:
    class Bare:
        history = None

    out = history_payload(Bare())
    assert out["available"] is False
