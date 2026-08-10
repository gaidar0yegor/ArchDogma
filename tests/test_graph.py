"""Unit tests for the Tier 2 import graph.

Covers the four things that make a graph trustworthy: names resolve the way
`import` would resolve them, edges point where the source says they point,
cycles are found without recursing to death, and coupling metrics agree with
the edges they are derived from.
"""

from __future__ import annotations

import ast
from pathlib import Path

from archdogma.probe.graph import (
    build_graph,
    count_module_sloc,
    count_top_level_defs,
    extract_imports,
    find_cycles,
    module_name_for,
)


def write_pkg(root: Path, files: dict[str, str]) -> list[Path]:
    """Materialise a package tree from {relative path: source} and return paths.

    Any directory holding a listed file gets an `__init__.py` unless the
    mapping supplies one, so the package chain resolves like a real project.
    """
    written: list[Path] = []
    for rel, source in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        written.append(path)

    for rel in list(files):
        parent = (root / rel).parent
        while parent != root:
            init = parent / "__init__.py"
            if not init.exists():
                init.write_text("", encoding="utf-8")
                written.append(init)
            parent = parent.parent
    return sorted(set(written))


# ---------------------------------------------------------------------------
# module_name_for
# ---------------------------------------------------------------------------


def _src_layout(tmp_path: Path) -> Path:
    """Build a real src-layout: `src/` is a plain directory, `app/` a package.

    Written by hand rather than via `write_pkg`, because the absence of
    `src/__init__.py` is the whole point — that absence is what stops the
    dotted name at `app`.
    """
    core = tmp_path / "src" / "app" / "core"
    core.mkdir(parents=True)
    (tmp_path / "src" / "app" / "__init__.py").write_text("", encoding="utf-8")
    (core / "__init__.py").write_text("", encoding="utf-8")
    (core / "engine.py").write_text("", encoding="utf-8")
    return tmp_path


def test_module_name_follows_package_chain(tmp_path: Path) -> None:
    _src_layout(tmp_path)
    path = tmp_path / "src" / "app" / "core" / "engine.py"
    assert module_name_for(path) == "app.core.engine"


def test_module_name_for_package_init(tmp_path: Path) -> None:
    _src_layout(tmp_path)
    path = tmp_path / "src" / "app" / "core" / "__init__.py"
    assert module_name_for(path) == "app.core"


def test_module_name_stops_at_the_first_non_package_directory(
    tmp_path: Path,
) -> None:
    """`src/` has no __init__.py, so it must not appear in the dotted name."""
    _src_layout(tmp_path)
    name = module_name_for(tmp_path / "src" / "app" / "core" / "engine.py")
    assert not name.startswith("src")


def test_module_name_outside_package_is_bare_stem(tmp_path: Path) -> None:
    script = tmp_path / "release.py"
    script.write_text("", encoding="utf-8")
    assert module_name_for(script) == "release"


# ---------------------------------------------------------------------------
# extract_imports
# ---------------------------------------------------------------------------


def test_extract_plain_import() -> None:
    refs = extract_imports(ast.parse("import a.b.c\n"))
    assert len(refs) == 1
    assert refs[0].module == "a.b.c"
    assert refs[0].level == 0
    assert refs[0].names == ()


def test_extract_multiple_names_in_one_import() -> None:
    refs = extract_imports(ast.parse("import os, sys\n"))
    assert sorted(r.module or "" for r in refs) == ["os", "sys"]


def test_extract_from_import_records_names() -> None:
    refs = extract_imports(ast.parse("from a.b import c, d\n"))
    assert refs[0].module == "a.b"
    assert refs[0].names == ("c", "d")


def test_extract_relative_import_records_level() -> None:
    refs = extract_imports(ast.parse("from ..pkg import thing\n"))
    assert refs[0].level == 2
    assert refs[0].module == "pkg"


def test_extract_bare_relative_import_has_no_module() -> None:
    refs = extract_imports(ast.parse("from . import sibling\n"))
    assert refs[0].module is None
    assert refs[0].level == 1
    assert refs[0].names == ("sibling",)


def test_extract_finds_imports_inside_functions() -> None:
    src = "def f():\n    import json\n    return json\n"
    refs = extract_imports(ast.parse(src))
    assert [r.module for r in refs] == ["json"]


def test_extract_finds_imports_in_type_checking_block() -> None:
    src = "if TYPE_CHECKING:\n    from a import B\n"
    refs = extract_imports(ast.parse(src))
    assert refs[0].module == "a"


def test_extract_records_line_numbers() -> None:
    refs = extract_imports(ast.parse("\n\nimport os\n"))
    assert refs[0].line == 3


# ---------------------------------------------------------------------------
# sloc / def counting
# ---------------------------------------------------------------------------


def test_sloc_skips_blanks_and_comments() -> None:
    src = "x = 1\n\n# a comment\ny = 2\n"
    assert count_module_sloc(ast.parse(src), src) == 2


def test_sloc_skips_module_docstring() -> None:
    src = '"""Doc\n\nspanning lines.\n"""\nx = 1\n'
    assert count_module_sloc(ast.parse(src), src) == 1


def test_sloc_skips_function_docstring() -> None:
    src = 'def f():\n    """Doc."""\n    return 1\n'
    assert count_module_sloc(ast.parse(src), src) == 2


def test_top_level_defs_counts_functions_and_classes() -> None:
    src = "def a(): pass\nclass B: pass\nasync def c(): pass\nx = 1\n"
    assert count_top_level_defs(ast.parse(src)) == 3


def test_top_level_defs_ignores_nested() -> None:
    src = "def outer():\n    def inner(): pass\n    return inner\n"
    assert count_top_level_defs(ast.parse(src)) == 1


# ---------------------------------------------------------------------------
# Edge resolution
# ---------------------------------------------------------------------------


def test_absolute_import_creates_internal_edge(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {
            "app/a.py": "from app import b\n",
            "app/b.py": "",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.a"] == ("app.b",)


def test_from_module_import_symbol_resolves_to_package(tmp_path: Path) -> None:
    """`from app.b import thing` where `thing` is a symbol, not a module."""
    paths = write_pkg(
        tmp_path,
        {
            "app/a.py": "from app.b import thing\n",
            "app/b.py": "thing = 1\n",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.a"] == ("app.b",)


def test_from_package_import_module_prefers_the_module(tmp_path: Path) -> None:
    """`from app import b` must point at module app.b, not package app."""
    paths = write_pkg(
        tmp_path,
        {
            "app/a.py": "from app import b\n",
            "app/b.py": "",
        },
    )
    graph = build_graph(paths)
    assert "app.b" in graph.edges["app.a"]
    assert "app" not in graph.edges["app.a"]


def test_relative_import_resolves(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {
            "app/core/a.py": "from . import b\n",
            "app/core/b.py": "",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.core.a"] == ("app.core.b",)


def test_parent_relative_import_resolves(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {
            "app/core/a.py": "from ..util import helper\n",
            "app/util/helper.py": "",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.core.a"] == ("app.util.helper",)


def test_multi_name_from_import_resolves_every_name(tmp_path: Path) -> None:
    """`from app import a, b` is two dependencies, not one."""
    paths = write_pkg(
        tmp_path,
        {
            "app/caller.py": "from app import a, b\n",
            "app/a.py": "",
            "app/b.py": "",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.caller"] == ("app.a", "app.b")


def test_mixed_module_and_symbol_import_also_depends_on_the_package(
    tmp_path: Path,
) -> None:
    """One name is a module, one is a symbol — both dependencies are real."""
    paths = write_pkg(
        tmp_path,
        {
            "app/__init__.py": "VERSION = '1'\n",
            "app/caller.py": "from app import a, VERSION\n",
            "app/a.py": "",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.caller"] == ("app", "app.a")


def test_import_of_unscanned_submodule_falls_back_to_known_prefix(
    tmp_path: Path,
) -> None:
    """`import app.core.missing` still executes `app.core`."""
    paths = write_pkg(
        tmp_path,
        {
            "app/caller.py": "import app.core.missing\n",
            "app/core/__init__.py": "",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.caller"] == ("app.core",)


def test_external_import_is_not_an_internal_edge(tmp_path: Path) -> None:
    paths = write_pkg(tmp_path, {"app/a.py": "import requests\nimport os\n"})
    graph = build_graph(paths)
    assert graph.edges["app.a"] == ()
    assert set(graph.external["app.a"]) == {"requests", "os"}


def test_external_records_top_level_distribution_name(tmp_path: Path) -> None:
    paths = write_pkg(tmp_path, {"app/a.py": "from yaml.loader import SafeLoader\n"})
    graph = build_graph(paths)
    assert graph.external["app.a"] == ("yaml",)


def test_self_import_does_not_create_an_edge(tmp_path: Path) -> None:
    paths = write_pkg(tmp_path, {"app/a.py": "import app.a\n"})
    graph = build_graph(paths)
    assert graph.edges["app.a"] == ()


def test_duplicate_imports_counted_once(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {
            "app/a.py": "from app import b\nfrom app.b import thing\n",
            "app/b.py": "thing = 1\n",
        },
    )
    graph = build_graph(paths)
    assert graph.edges["app.a"] == ("app.b",)


def test_syntax_error_is_recorded_not_raised(tmp_path: Path) -> None:
    paths = write_pkg(tmp_path, {"app/a.py": "def broken(\n"})
    graph = build_graph(paths)
    assert "app.a" not in graph.modules
    assert any("a.py" in k for k in graph.parse_errors)


def test_ambiguous_name_creates_no_edges(tmp_path: Path) -> None:
    """Two loose scripts with the same stem must not fabricate an edge."""
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "util.py").write_text("", encoding="utf-8")
    (tmp_path / "two" / "util.py").write_text("", encoding="utf-8")
    caller = tmp_path / "main.py"
    caller.write_text("import util\n", encoding="utf-8")
    graph = build_graph(
        [tmp_path / "one" / "util.py", tmp_path / "two" / "util.py", caller]
    )
    assert "util" in graph.ambiguous_names
    assert graph.edges["main"] == ()


# ---------------------------------------------------------------------------
# Coupling metrics
# ---------------------------------------------------------------------------


def test_afferent_and_efferent_agree_with_edges(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {
            "app/core.py": "",
            "app/a.py": "from app import core\n",
            "app/b.py": "from app import core\n",
            "app/c.py": "from app import core, a\n",
        },
    )
    graph = build_graph(paths)
    assert graph.afferent("app.core") == 3
    assert graph.efferent("app.core") == 0
    assert graph.efferent("app.c") == 2


def test_instability_zero_for_pure_dependency(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {"app/core.py": "", "app/a.py": "from app import core\n"},
    )
    graph = build_graph(paths)
    assert graph.instability("app.core") == 0.0
    assert graph.instability("app.a") == 1.0


def test_instability_of_isolated_module_is_zero(tmp_path: Path) -> None:
    paths = write_pkg(tmp_path, {"app/lonely.py": ""})
    graph = build_graph(paths)
    assert graph.instability("app.lonely") == 0.0


# ---------------------------------------------------------------------------
# Cycles
# ---------------------------------------------------------------------------


def test_no_cycle_in_a_chain() -> None:
    assert find_cycles({"a": ("b",), "b": ("c",), "c": ()}) == ()


def test_two_module_cycle() -> None:
    assert find_cycles({"a": ("b",), "b": ("a",)}) == (("a", "b"),)


def test_three_module_cycle() -> None:
    cycles = find_cycles({"a": ("b",), "b": ("c",), "c": ("a",)})
    assert cycles == (("a", "b", "c"),)


def test_self_loop_is_not_a_cycle() -> None:
    assert find_cycles({"a": ("a",)}) == ()


def test_two_disjoint_cycles_both_reported() -> None:
    cycles = find_cycles(
        {"a": ("b",), "b": ("a",), "x": ("y",), "y": ("x",), "z": ()}
    )
    assert cycles == (("a", "b"), ("x", "y"))


def test_deep_chain_does_not_blow_the_stack() -> None:
    """Iterative Tarjan: a 5000-deep chain must not raise RecursionError."""
    depth = 5000
    edges = {f"m{i}": (f"m{i + 1}",) for i in range(depth)}
    edges[f"m{depth}"] = ()
    assert find_cycles(edges) == ()


def test_deep_cycle_is_found_without_recursion() -> None:
    depth = 5000
    edges = {f"m{i}": (f"m{i + 1}",) for i in range(depth)}
    edges[f"m{depth}"] = ("m0",)
    cycles = find_cycles(edges)
    assert len(cycles) == 1
    assert len(cycles[0]) == depth + 1


def test_cycle_detected_end_to_end(tmp_path: Path) -> None:
    paths = write_pkg(
        tmp_path,
        {
            "app/a.py": "from app import b\n",
            "app/b.py": "from app import a\n",
        },
    )
    graph = build_graph(paths)
    assert graph.cycles == (("app.a", "app.b"),)
    assert graph.cycle_for("app.a") == ("app.a", "app.b")
    assert graph.cycle_for("app.a") == graph.cycle_for("app.b")


def test_cycle_for_returns_none_outside_a_cycle(tmp_path: Path) -> None:
    paths = write_pkg(tmp_path, {"app/a.py": "", "app/b.py": "from app import a\n"})
    graph = build_graph(paths)
    assert graph.cycle_for("app.b") is None
