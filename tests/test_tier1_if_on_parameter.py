"""Unit tests for the if-on-parameter detector."""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    DEFAULT_IF_ON_PARAMETER_BRANCHES,
    detect_if_on_parameter,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


# ---------------------------------------------------------------------------
# Below threshold — no tag
# ---------------------------------------------------------------------------


def test_no_ifs_no_tag() -> None:
    func = _first_func("def f(x):\n    return x\n")
    assert detect_if_on_parameter(func) is None


def test_two_branches_no_tag() -> None:
    source = (
        "def f(mode):\n"
        "    if mode == 'a':\n"
        "        return 1\n"
        "    elif mode == 'b':\n"
        "        return 2\n"
    )
    assert detect_if_on_parameter(_first_func(source)) is None


def test_nested_if_not_counted_as_extra_branch() -> None:
    """A nested if inside a branch body should not inflate the pivot count."""
    source = (
        "def f(mode):\n"
        "    if mode == 'a':\n"
        "        if mode == 'a':\n"  # same pivot but nested — not a new top-level branch
        "            return 1\n"
        "    elif mode == 'b':\n"
        "        return 2\n"
    )
    # 2 direct branches — below threshold 3
    assert detect_if_on_parameter(_first_func(source)) is None


# ---------------------------------------------------------------------------
# At/above threshold — tag emitted
# ---------------------------------------------------------------------------


def test_three_branches_triggers() -> None:
    source = (
        "def f(mode):\n"
        "    if mode == 'a':\n"
        "        return 1\n"
        "    elif mode == 'b':\n"
        "        return 2\n"
        "    elif mode == 'c':\n"
        "        return 3\n"
    )
    tag = detect_if_on_parameter(_first_func(source))
    assert tag is not None
    assert tag.name == "if-on-parameter"
    assert "mode" in tag.detail
    assert "3" in tag.detail


def test_literal_on_left_side_detected() -> None:
    """Reversed comparison: `'x' == param` is also caught."""
    source = (
        "def f(flag):\n"
        "    if 'a' == flag:\n"
        "        pass\n"
        "    elif 'b' == flag:\n"
        "        pass\n"
        "    elif 'c' == flag:\n"
        "        pass\n"
    )
    tag = detect_if_on_parameter(_first_func(source))
    assert tag is not None
    assert "flag" in tag.detail


def test_different_params_not_grouped() -> None:
    """Two different params each with 2 branches should not trigger (threshold=3)."""
    source = (
        "def f(x, y):\n"
        "    if x == 1:\n"
        "        pass\n"
        "    elif x == 2:\n"
        "        pass\n"
        "    if y == 'a':\n"
        "        pass\n"
        "    elif y == 'b':\n"
        "        pass\n"
    )
    assert detect_if_on_parameter(_first_func(source)) is None


def test_isinstance_check_not_caught() -> None:
    """isinstance(x, Foo) is NOT a `x == literal` pattern — must not trigger."""
    source = (
        "def f(x):\n"
        "    if isinstance(x, int):\n"
        "        pass\n"
        "    elif isinstance(x, str):\n"
        "        pass\n"
        "    elif isinstance(x, float):\n"
        "        pass\n"
    )
    assert detect_if_on_parameter(_first_func(source)) is None


def test_custom_threshold() -> None:
    """With threshold=2, two branches should trigger."""
    source = (
        "def f(t):\n"
        "    if t == 'x':\n"
        "        return 1\n"
        "    elif t == 'y':\n"
        "        return 2\n"
    )
    assert detect_if_on_parameter(_first_func(source), threshold=2) is not None
    assert detect_if_on_parameter(_first_func(source), threshold=3) is None


def test_inner_function_not_counted() -> None:
    """Branches inside a nested def are not counted for the outer function."""
    source = (
        "def outer(mode):\n"
        "    def inner(mode):\n"
        "        if mode == 'a':\n"
        "            pass\n"
        "        elif mode == 'b':\n"
        "            pass\n"
        "        elif mode == 'c':\n"
        "            pass\n"
        "    return inner\n"
    )
    # outer has 0 branches; inner has 3 but is a separate scope
    assert detect_if_on_parameter(_first_func(source)) is None
