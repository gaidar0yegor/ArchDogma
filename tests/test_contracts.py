"""Tests for architecture contracts — parsing, semantics, history pricing."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from archdogma.cli import main
from archdogma.contracts import (
    Contract,
    ContractConfigError,
    check_contract,
    load_contracts,
    run_contracts,
)

from tests.test_graph import write_pkg
from tests.test_history import git
from tests.test_tier2 import graph_from_edges


def write_config(root: Path, body: str) -> Path:
    p = root / "pyproject.toml"
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


def test_missing_pyproject_means_no_contracts(tmp_path: Path) -> None:
    assert load_contracts(tmp_path / "pyproject.toml") == []


def test_missing_table_means_no_contracts(tmp_path: Path) -> None:
    p = write_config(tmp_path, "[project]\nname = 'x'\n")
    assert load_contracts(p) == []


def test_forbidden_contract_parses(tmp_path: Path) -> None:
    p = write_config(
        tmp_path,
        '[[tool.archdogma.contracts]]\nname = "n"\ntype = "forbidden"\n'
        'source = ["app.core"]\nforbidden = ["app.web"]\n',
    )
    (c,) = load_contracts(p)
    assert c.type == "forbidden"
    assert c.source == ("app.core",)


def test_string_shorthand_becomes_tuple(tmp_path: Path) -> None:
    p = write_config(
        tmp_path,
        '[[tool.archdogma.contracts]]\ntype = "forbidden"\n'
        'source = "app.core"\nforbidden = "app.web"\n',
    )
    (c,) = load_contracts(p)
    assert c.source == ("app.core",)
    assert c.name  # default name assigned


def test_unknown_type_is_fatal(tmp_path: Path) -> None:
    p = write_config(
        tmp_path, '[[tool.archdogma.contracts]]\ntype = "vibes"\n'
    )
    with pytest.raises(ContractConfigError):
        load_contracts(p)


def test_single_layer_is_fatal(tmp_path: Path) -> None:
    """A silently useless contract is a gate that silently opened."""
    p = write_config(
        tmp_path,
        '[[tool.archdogma.contracts]]\ntype = "layers"\nlayers = ["only"]\n',
    )
    with pytest.raises(ContractConfigError):
        load_contracts(p)


# ---------------------------------------------------------------------------
# Semantics
# ---------------------------------------------------------------------------


def test_forbidden_flags_subtree_import() -> None:
    graph = graph_from_edges({"app.core.engine": ("app.web.views",)})
    c = Contract(name="n", type="forbidden", source=("app.core",), forbidden=("app.web",))
    (v,) = check_contract(c, graph)
    assert v.importer == "app.core.engine"
    assert v.imported == "app.web.views"


def test_forbidden_ignores_other_directions() -> None:
    graph = graph_from_edges({"app.web.views": ("app.core.engine",)})
    c = Contract(name="n", type="forbidden", source=("app.core",), forbidden=("app.web",))
    assert check_contract(c, graph) == []


def test_layers_flags_upward_import_only() -> None:
    # cli (high) -> core (low) is fine; core -> cli is the breach.
    edges = {"app.cli": ("app.core",), "app.core": ("app.cli",)}
    graph = graph_from_edges(edges)
    c = Contract(name="n", type="layers", layers=("app.cli", "app.core"))
    violations = check_contract(c, graph)
    assert len(violations) == 1
    assert violations[0].importer == "app.core"


def test_layers_ignores_modules_outside_the_layering() -> None:
    graph = graph_from_edges({"app.core": ("app.util",)})
    c = Contract(name="n", type="layers", layers=("app.cli", "app.core"))
    assert check_contract(c, graph) == []


def test_independence_flags_both_directions() -> None:
    edges = {"app.a.x": ("app.b.y",), "app.b.y": ("app.a.x",)}
    graph = graph_from_edges(edges)
    c = Contract(name="n", type="independence", modules=("app.a", "app.b"))
    assert len(check_contract(c, graph)) == 2


def test_independence_allows_internal_imports() -> None:
    graph = graph_from_edges({"app.a.x": ("app.a.y",)})
    c = Contract(name="n", type="independence", modules=("app.a", "app.b"))
    assert check_contract(c, graph) == []


def test_longest_prefix_wins() -> None:
    """A module under pkg.sub is attributed to pkg.sub, not pkg."""
    graph = graph_from_edges({"pkg.sub.mod": ("pkg.other",)})
    c = Contract(
        name="n", type="independence", modules=("pkg", "pkg.sub")
    )
    # pkg.sub.mod belongs to pkg.sub; pkg.other belongs to pkg — cross-import.
    assert len(check_contract(c, graph)) == 1


def test_prefix_does_not_match_name_fragments() -> None:
    """'app.web' must not claim 'app.webhooks'."""
    graph = graph_from_edges({"app.core": ("app.webhooks",)})
    c = Contract(name="n", type="forbidden", source=("app.core",), forbidden=("app.web",))
    assert check_contract(c, graph) == []


# ---------------------------------------------------------------------------
# End-to-end with history pricing
# ---------------------------------------------------------------------------


CONFIG = """
[[tool.archdogma.contracts]]
name = "core must not import web"
type = "forbidden"
source = ["app.core"]
forbidden = ["app.web"]
"""


def _violating_repo(tmp_path: Path) -> Path:
    """Violation committed at t0; an unrelated commit 200 days later.

    Ages are measured from the newest commit in the repository (by design —
    see history.py), so the second commit is what makes the violating file
    200 days old instead of 0.
    """
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(
        ["git", "-C", str(root), "init", "-q", "-b", "main"],
        check=True,
        capture_output=True,
    )
    write_pkg(
        root,
        {
            "app/core/engine.py": "from app.web import views\n",
            "app/web/views.py": "X = 1\n",
        },
    )
    write_config(root, CONFIG)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init", when=1700000000)
    (root / "app" / "unrelated.py").write_text("Y = 1\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "later work", when=1700000000 + 200 * 86400)
    return root


def test_run_contracts_prices_violation_with_history(tmp_path: Path) -> None:
    root = _violating_repo(tmp_path)
    report = run_contracts(root)
    assert report.history_available
    (v,) = report.violations
    assert v.importer == "app.core.engine"
    assert v.commits == 1
    assert v.days_since_change is not None


def test_run_contracts_without_git_reports_unpriced(tmp_path: Path) -> None:
    write_pkg(
        tmp_path,
        {
            "app/core/engine.py": "from app.web import views\n",
            "app/web/views.py": "",
        },
    )
    write_config(tmp_path, CONFIG)
    report = run_contracts(tmp_path)
    assert not report.history_available
    (v,) = report.violations
    assert v.commits is None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_no_contracts_is_not_a_pass(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": ""})
    result = CliRunner().invoke(main, ["contracts", str(tmp_path)])
    assert result.exit_code == 0
    assert "not a pass" in result.output


def test_cli_violation_fails_and_prints_history(tmp_path: Path) -> None:
    root = _violating_repo(tmp_path)
    result = CliRunner().invoke(main, ["contracts", str(root)])
    assert result.exit_code == 1
    assert "core must not import web" in result.output
    assert "importer history:" in result.output


def test_cli_json_carries_pricing_fields(tmp_path: Path) -> None:
    root = _violating_repo(tmp_path)
    result = CliRunner().invoke(
        main, ["contracts", str(root), "--format", "json", "--no-fail"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    (v,) = data["violations"]
    assert set(v) >= {
        "contract",
        "importer",
        "imported",
        "importer_commits",
        "importer_churn_percentile",
        "active",
    }


def test_fail_only_active_passes_on_dormant_violation(tmp_path: Path) -> None:
    """The 2023-era violation is reported but does not gate."""
    root = _violating_repo(tmp_path)  # committed at epoch 1700000000 (2023)
    result = CliRunner().invoke(
        main, ["contracts", str(root), "--fail-only-active", "--active-days", "30"]
    )
    assert result.exit_code == 0
    assert "core must not import web" in result.output  # still reported
    assert "dormant" in result.output


def test_fail_only_active_without_history_still_fails(tmp_path: Path) -> None:
    """Unknown is not dormant: no git means every violation gates."""
    write_pkg(
        tmp_path,
        {
            "app/core/engine.py": "from app.web import views\n",
            "app/web/views.py": "",
        },
    )
    write_config(tmp_path, CONFIG)
    result = CliRunner().invoke(
        main, ["contracts", str(tmp_path), "--fail-only-active"]
    )
    assert result.exit_code == 1


def test_cli_bad_config_exits_2(tmp_path: Path) -> None:
    write_pkg(tmp_path, {"app/a.py": ""})
    write_config(tmp_path, '[[tool.archdogma.contracts]]\ntype = "nope"\n')
    result = CliRunner().invoke(main, ["contracts", str(tmp_path)])
    assert result.exit_code == 2


def test_own_contracts_hold() -> None:
    """Dogfood: the contracts declared in our own pyproject pass."""
    report = run_contracts(Path("."), excludes=("tests/**", ".venv/**"))
    assert report.checked == 2
    assert report.violations == ()
