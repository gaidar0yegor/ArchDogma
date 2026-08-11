"""Tests for the agent-facing functions and the MCP server wiring.

The tool functions are plain functions returning dicts — tested directly,
no MCP client involved. The server test only asserts registration: the
protocol itself is the SDK's contract to keep, not ours.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from archdogma.agent import (
    MAX_FILES,
    analyze_modules,
    check_before_refactor,
    explain_dogma,
    list_dogmas,
    scan_functions,
)

from tests.test_graph import write_pkg
from tests.test_history import git


def make_repo(tmp_path: Path, files: dict[str, str], commits: int = 1) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(
        ["git", "-C", str(root), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
    )
    write_pkg(root, files)
    for i in range(commits):
        for rel in files:
            path = root / rel
            path.write_text(path.read_text() + f"\n# rev {i}\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", f"rev {i}", when=1700000000 + i * 86400)
    return root


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_nonexistent_root_is_an_error_payload() -> None:
    out = scan_functions("/definitely/not/a/path")
    assert "error" in out


def test_max_files_guard_refuses_not_stalls(tmp_path: Path, monkeypatch) -> None:
    import archdogma.agent as agent_mod

    monkeypatch.setattr(agent_mod, "MAX_FILES", 3)
    write_pkg(tmp_path, {f"app/m{i}.py": "" for i in range(6)})
    out = scan_functions(str(tmp_path))
    assert "error" in out
    assert "excludes" in out["error"]


def test_max_files_default_is_sane() -> None:
    assert MAX_FILES >= 1000


# ---------------------------------------------------------------------------
# scan_functions / analyze_modules
# ---------------------------------------------------------------------------


def test_scan_functions_carries_catalog_context(tmp_path: Path) -> None:
    src = tmp_path / "m.py"
    src.write_text(
        "def f(a, b, c, d, e, g, h):\n    return a\n", encoding="utf-8"
    )
    out = scan_functions(str(tmp_path))
    tags = [t for f in out["files"] for i in f.get("items", []) for t in i["tags"]]
    params = next(t for t in tags if t["name"] == "too-many-params")
    assert params["dogmas"] == ["long-parameter-list"]
    assert "long-parameter-list" in out["catalog"]["entries"]


def test_analyze_modules_states_history_absence(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": ""})
    out = analyze_modules(str(tmp_path))
    assert out["history"]["available"] is False
    assert "not evidence" in out["history"]["reason"]


def test_analyze_modules_reports_cycles(tmp_path: Path) -> None:
    write_pkg(
        tmp_path,
        {"app/a.py": "from app import b\n", "app/b.py": "from app import a\n"},
    )
    out = analyze_modules(str(tmp_path))
    assert out["cycles"] == [["app.a", "app.b"]]
    fired = {t["name"] for m in out["modules"] for t in m["tags"]}
    assert "circular-import" in fired


# ---------------------------------------------------------------------------
# explain_dogma / list_dogmas
# ---------------------------------------------------------------------------


def test_explain_dogma_returns_full_entry() -> None:
    out = explain_dogma("dry")
    match = out["matches"][0]
    assert match["id"] == "dry"
    assert "rendered" in match
    assert match["honest_verdict"]["break_when"]


def test_explain_dogma_miss_returns_suggestions() -> None:
    out = explain_dogma("solidd")
    assert "error" in out
    assert "solid" in out["suggestions"]


def test_list_dogmas_indexes_the_catalog() -> None:
    out = list_dogmas()
    ids = {d["id"] for d in out["dogmas"]}
    assert {"dry", "kiss", "tdd"} <= ids
    assert any(c["id"] == "bus-factor" for c in out["candidates"])


# ---------------------------------------------------------------------------
# check_before_refactor
# ---------------------------------------------------------------------------


def test_check_reports_dependents_and_metrics(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        {
            "app/core.py": "X = 1\n",
            "app/a.py": "from app import core\n",
            "app/b.py": "from app import core\n",
        },
    )
    out = check_before_refactor(str(root), "app/core.py")
    assert out["module"] == "app.core"
    assert set(out["dependents"]) == {"app.a", "app.b"}
    assert out["metrics"]["afferent"] == 2
    assert out["metrics"]["commits"] is not None


def test_check_relative_and_absolute_paths_agree(tmp_path: Path) -> None:
    root = make_repo(tmp_path, {"app/core.py": "X = 1\n"})
    rel = check_before_refactor(str(root), "app/core.py")
    abs_ = check_before_refactor(str(root), str(root / "app" / "core.py"))
    assert rel["module"] == abs_["module"] == "app.core"


def test_check_unknown_file_is_an_error(tmp_path: Path) -> None:
    root = make_repo(tmp_path, {"app/core.py": ""})
    out = check_before_refactor(str(root), "app/nope.py")
    assert "error" in out


def test_check_verdict_is_summary_not_new_information(tmp_path: Path) -> None:
    """Every verdict line must be derivable from fields in the payload."""
    root = make_repo(
        tmp_path,
        {
            "app/core.py": "X = 1\n",
            **{f"app/d{i}.py": "from app import core\n" for i in range(6)},
        },
    )
    out = check_before_refactor(str(root), "app/core.py")
    joined = " ".join(out["verdict"])
    if "modules import this one" in joined:
        assert out["metrics"]["afferent"] >= 5
    if "Single author" in joined:
        assert out["metrics"]["author_count"] == 1


def test_check_quiet_file_says_so(tmp_path: Path) -> None:
    root = make_repo(
        tmp_path,
        {"app/leaf.py": "X = 1\n", "app/core.py": "from app import leaf\n"},
    )
    out = check_before_refactor(str(root), "app/core.py")
    assert out["verdict"] == [
        "No elevated risk signals from the import graph or the history."
    ]


def test_check_temporal_partners_exclude_importing_pairs(tmp_path: Path) -> None:
    """Co-changing files that import each other are documented coupling."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(
        ["git", "-C", str(root), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
    )
    write_pkg(
        root,
        {"app/a.py": "from app import b\n", "app/b.py": "X = 1\n"},
    )
    for i in range(6):
        (root / "app" / "a.py").write_text(
            f"from app import b\nY = {i}\n", encoding="utf-8"
        )
        (root / "app" / "b.py").write_text(f"X = {i}\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", f"rev {i}", when=1700000000 + i * 86400)
    out = check_before_refactor(str(root), "app/a.py")
    assert all(p["module"] != "app.b" for p in out["temporal_partners"])


# ---------------------------------------------------------------------------
# MCP wiring
# ---------------------------------------------------------------------------


def test_build_server_registers_the_five_tools() -> None:
    pytest.importorskip("mcp")
    from archdogma.agent import build_server

    server = build_server()
    # The SDK's public surface for listing registered tools varies across
    # versions; the tool manager is the stable-enough seam.
    names = set()
    for attr in ("_tool_manager", "tool_manager"):
        manager = getattr(server, attr, None)
        if manager is not None and hasattr(manager, "list_tools"):
            names = {t.name for t in manager.list_tools()}
            break
    assert {
        "scan_functions",
        "analyze_modules",
        "explain_dogma",
        "check_before_refactor",
        "list_dogmas",
    } <= names


def test_all_payloads_are_json_serializable(tmp_path: Path) -> None:
    root = make_repo(tmp_path, {"app/core.py": "X = 1\n"})
    for payload in (
        scan_functions(str(root)),
        analyze_modules(str(root)),
        explain_dogma("kiss"),
        check_before_refactor(str(root), "app/core.py"),
        list_dogmas(),
    ):
        json.dumps(payload)


# ---------------------------------------------------------------------------
# Review-round regressions (adversarial review before the first PR)
# ---------------------------------------------------------------------------


def test_guard_honours_excludes(tmp_path: Path, monkeypatch) -> None:
    """The refusal message recommends excludes, so the guard must apply them."""
    import archdogma.agent as agent_mod

    monkeypatch.setattr(agent_mod, "MAX_FILES", 3)
    write_pkg(tmp_path, {f"vendor/m{i}.py": "" for i in range(6)})
    write_pkg(tmp_path, {"app/main.py": ""})
    out = scan_functions(str(tmp_path), excludes=["vendor/*"])
    assert "error" not in out


def test_check_before_refactor_accepts_excludes(tmp_path: Path, monkeypatch) -> None:
    import archdogma.agent as agent_mod

    monkeypatch.setattr(agent_mod, "MAX_FILES", 3)
    root = make_repo(tmp_path, {"app/core.py": "X = 1\n"})
    write_pkg(root, {f"vendor/m{i}.py": "" for i in range(6)})
    out = check_before_refactor(str(root), "app/core.py", excludes=["vendor/*"])
    assert out.get("module") == "app.core"


def test_partner_floors_match_the_detector(tmp_path: Path) -> None:
    """3 shared commits over a 3-commit lifetime is the tiny-denominator
    noise the detector's floors exist to filter; the pre-flight check must
    not resurrect it."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(
        ["git", "-C", str(root), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
    )
    write_pkg(root, {"app/x.py": "A = 0\n", "app/y.py": "B = 0\n"})
    for i in range(3):
        (root / "app" / "x.py").write_text(f"A = {i}\n", encoding="utf-8")
        (root / "app" / "y.py").write_text(f"B = {i}\n", encoding="utf-8")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", f"rev {i}", when=1700000000 + i * 86400)
    out = check_before_refactor(str(root), "app/x.py")
    assert out["temporal_partners"] == []


def test_no_history_verdict_is_never_a_clean_bill(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/core.py": "X = 1\n"})
    out = check_before_refactor(str(tmp_path), "app/core.py")
    joined = " ".join(out["verdict"])
    assert "NOT available" in joined
    assert "not evidence" in joined


def test_project_root_as_single_file(tmp_path: Path) -> None:
    src = tmp_path / "solo.py"
    src.write_text("X = 1\n", encoding="utf-8")
    out = check_before_refactor(str(src), "solo.py")
    assert out.get("module") == "solo"


def test_foreign_catalog_use_is_stated_not_silent(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/m.py": "def f(a, b, c, d, e, g, h):\n    return a\n"})
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "dogmas.yaml").write_text(
        "schema_version: 1\ndogmas:\n"
        "  - id: private-rule\n    number: 1\n    title: Private\n"
        "    status: draft\n    related_tags: [private-tag]\n",
        encoding="utf-8",
    )
    out = scan_functions(str(tmp_path))
    assert "note" in out["catalog"]
    assert "not consulted" in out["catalog"]["note"]
