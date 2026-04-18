"""Tests for file-level Probe — methods, nested functions, qualified names.

This is the ADR-nonexistent-yet milestone: the walker now addresses more
than `def` at module scope. The same `probe_function` path should work,
just with dotted qualified names instead of bare ones.
"""

from __future__ import annotations

import ast
from pathlib import Path

from archdogma.probe.walker import (
    DiscoveredFunction,
    find_function,
    list_all_functions,
    parse_file,
    probe_function,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "file_probe_sample.py"


def _tree() -> ast.Module:
    return parse_file(FIXTURE)


# ---------------------------------------------------------------------------
# list_all_functions — qualified names, source order, kind
# ---------------------------------------------------------------------------


def test_lists_top_level_functions() -> None:
    names = [df.qualified_name for df in list_all_functions(_tree())]
    assert "top_level_plain" in names
    assert "top_level_async" in names
    assert "with_nested" in names


def test_lists_class_methods_with_qualified_name() -> None:
    names = [df.qualified_name for df in list_all_functions(_tree())]
    assert "Outer.regular_method" in names
    assert "Outer.class_method" in names
    assert "Outer.static_method" in names


def test_lists_nested_classes_methods() -> None:
    names = [df.qualified_name for df in list_all_functions(_tree())]
    # Inner is a class inside Outer; its method is Outer.Inner.deep_method.
    assert "Outer.Inner.deep_method" in names


def test_lists_nested_functions_inside_methods() -> None:
    names = [df.qualified_name for df in list_all_functions(_tree())]
    # helper is a nested def inside Outer.regular_method.
    assert "Outer.regular_method.helper" in names


def test_lists_double_nested_functions() -> None:
    names = [df.qualified_name for df in list_all_functions(_tree())]
    assert "with_nested.child" in names
    assert "with_nested.child.grandchild" in names


def test_kind_field_distinguishes_function_method_nested() -> None:
    by_name = {df.qualified_name: df for df in list_all_functions(_tree())}
    assert by_name["top_level_plain"].kind == "function"
    assert by_name["Outer.regular_method"].kind == "method"
    assert by_name["Outer.regular_method.helper"].kind == "nested"
    assert by_name["Outer.Inner.deep_method"].kind == "method"
    assert by_name["with_nested.child"].kind == "nested"


def test_container_points_to_enclosing_scope() -> None:
    by_name = {df.qualified_name: df for df in list_all_functions(_tree())}
    assert by_name["top_level_plain"].container is None
    assert by_name["Outer.regular_method"].container == "Outer"
    assert (
        by_name["Outer.regular_method.helper"].container
        == "Outer.regular_method"
    )
    assert by_name["Outer.Inner.deep_method"].container == "Outer.Inner"
    assert by_name["with_nested.child.grandchild"].container == "with_nested.child"


def test_source_order_preserved() -> None:
    """Listing order should match how the file reads, depth-first.
    Top-level `top_level_plain` appears before `top_level_async`, which
    appears before anything inside `Outer`."""
    names = [df.qualified_name for df in list_all_functions(_tree())]
    pos = {n: i for i, n in enumerate(names)}
    assert pos["top_level_plain"] < pos["top_level_async"]
    assert pos["top_level_async"] < pos["Outer.regular_method"]
    # Method ordering inside Outer reflects source order.
    assert pos["Outer.regular_method"] < pos["Outer.class_method"]
    assert pos["Outer.class_method"] < pos["Outer.static_method"]
    # Nested-def follows its enclosing method.
    assert pos["Outer.regular_method"] < pos["Outer.regular_method.helper"]


# ---------------------------------------------------------------------------
# find_function — dotted name resolution
# ---------------------------------------------------------------------------


def test_find_top_level_function() -> None:
    node = find_function(_tree(), "top_level_plain")
    assert node is not None
    assert node.name == "top_level_plain"


def test_find_async_function() -> None:
    node = find_function(_tree(), "top_level_async")
    assert node is not None
    assert isinstance(node, ast.AsyncFunctionDef)


def test_find_method_by_dotted_name() -> None:
    node = find_function(_tree(), "Outer.regular_method")
    assert node is not None
    assert node.name == "regular_method"


def test_find_nested_method_in_inner_class() -> None:
    node = find_function(_tree(), "Outer.Inner.deep_method")
    assert node is not None
    assert node.name == "deep_method"


def test_find_nested_function_inside_method() -> None:
    node = find_function(_tree(), "Outer.regular_method.helper")
    assert node is not None
    assert node.name == "helper"


def test_find_returns_none_for_unknown() -> None:
    assert find_function(_tree(), "does_not_exist") is None
    assert find_function(_tree(), "Outer.does_not_exist") is None
    assert find_function(_tree(), "NotAClass.method") is None


def test_find_returns_none_for_class_name_alone() -> None:
    """Classes are not addressable as functions — `Outer` alone must miss."""
    assert find_function(_tree(), "Outer") is None
    assert find_function(_tree(), "Outer.Inner") is None


def test_find_returns_none_for_partial_match() -> None:
    """`regular_method` bare should NOT match `Outer.regular_method`.
    We don't do "search anywhere"; that would be surprising and ambiguous."""
    assert find_function(_tree(), "regular_method") is None
    assert find_function(_tree(), "helper") is None


# ---------------------------------------------------------------------------
# probe_function — detectors run on methods and nested defs
# ---------------------------------------------------------------------------


def test_probe_method_runs_detectors() -> None:
    """regular_method has 6 params (excluding self) — should trip too-many-params."""
    result = probe_function(FIXTURE, "Outer.regular_method")
    assert result is not None
    assert result.function_name == "Outer.regular_method"
    tag_names = {t.name for t in result.tags}
    assert "too-many-params" in tag_names


def test_probe_method_excludes_self_from_param_count() -> None:
    """regular_method signature is (self, a, b, c, d, e, f) — 6 real params,
    not 7. The detector's self-exclusion rule must apply on methods too."""
    result = probe_function(FIXTURE, "Outer.regular_method")
    assert result is not None
    tmp = [t for t in result.tags if t.name == "too-many-params"]
    assert tmp
    assert "6 parameters" in tmp[0].detail


def test_probe_classmethod_excludes_cls() -> None:
    """class_method is (cls, a) — after dropping cls, only 1 real param. No tag."""
    result = probe_function(FIXTURE, "Outer.class_method")
    assert result is not None
    assert not any(t.name == "too-many-params" for t in result.tags)


def test_probe_staticmethod_treated_as_regular() -> None:
    """static_method() has 0 params — nothing to flag, but it resolves."""
    result = probe_function(FIXTURE, "Outer.static_method")
    assert result is not None
    assert result.tags == ()


def test_probe_nested_function_works() -> None:
    result = probe_function(FIXTURE, "Outer.regular_method.helper")
    assert result is not None
    assert result.function_name == "Outer.regular_method.helper"
    # helper takes one arg — no tags.
    assert result.tags == ()


def test_probe_unknown_qualified_name_returns_none() -> None:
    assert probe_function(FIXTURE, "Outer.does_not_exist") is None
    assert probe_function(FIXTURE, "foo.bar.baz") is None


# ---------------------------------------------------------------------------
# DiscoveredFunction is hashable & frozen (defensive)
# ---------------------------------------------------------------------------


def test_discovered_function_is_frozen() -> None:
    df = list_all_functions(_tree())[0]
    assert isinstance(df, DiscoveredFunction)
    import dataclasses

    try:
        dataclasses.replace(df, qualified_name="oops")  # allowed — returns a new one
    except dataclasses.FrozenInstanceError:  # pragma: no cover
        # replace() on a frozen dataclass must still work; direct mutation must not.
        pass
    # Direct mutation should raise.
    try:
        df.qualified_name = "x"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("DiscoveredFunction must be frozen")
