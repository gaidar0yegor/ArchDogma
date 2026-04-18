"""Unit tests for the deep-nesting detector.

Uses inline Python source strings parsed with ast.parse(), then grabs the
first top-level function. Keeps tests readable and self-contained.
"""

from __future__ import annotations

import ast

import pytest

from archdogma.probe.tags.tier1 import (
    DEFAULT_DEEP_NESTING_THRESHOLD,
    Tag,
    detect_deep_nesting,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef), (
        f"fixture must start with def/async def, got {type(node).__name__}"
    )
    return node


# ---------------------------------------------------------------------------
# Below threshold
# ---------------------------------------------------------------------------


def test_empty_body_no_tag() -> None:
    func = _first_func("def f():\n    pass\n")
    assert detect_deep_nesting(func) is None


def test_single_if_no_tag() -> None:
    func = _first_func("def f(x):\n    if x:\n        return 1\n")
    assert detect_deep_nesting(func) is None


def test_three_deep_no_tag() -> None:
    """Three nested ifs → max depth 3 → below threshold 4."""
    source = (
        "def f(a, b, c):\n"
        "    if a:\n"
        "        if b:\n"
        "            if c:\n"
        "                return 1\n"
    )
    assert detect_deep_nesting(_first_func(source)) is None


def test_elif_chain_is_flat() -> None:
    """A long elif chain must stay at depth 1 — elif is not nesting."""
    source = (
        "def f(x):\n"
        "    if x == 1:\n"
        "        return 1\n"
        "    elif x == 2:\n"
        "        return 2\n"
        "    elif x == 3:\n"
        "        return 3\n"
        "    elif x == 4:\n"
        "        return 4\n"
        "    else:\n"
        "        return 0\n"
    )
    assert detect_deep_nesting(_first_func(source)) is None


# ---------------------------------------------------------------------------
# At / above threshold
# ---------------------------------------------------------------------------


def test_four_deep_triggers_tag() -> None:
    """Four nested ifs → max depth 4 → meets default threshold."""
    source = (
        "def f(a, b, c, d):\n"
        "    if a:\n"
        "        if b:\n"
        "            if c:\n"
        "                if d:\n"
        "                    return 1\n"
    )
    tag = detect_deep_nesting(_first_func(source))
    assert isinstance(tag, Tag)
    assert tag.name == "deep-nesting"
    assert "4 levels deep" in tag.detail


def test_five_deep_mixed_control_flow() -> None:
    """if + for + while + try + nested block → depth 5, triggers."""
    source = (
        "def f(x):\n"
        "    if x:\n"
        "        for i in x:\n"
        "            while i > 0:\n"
        "                try:\n"
        "                    if i == 1:\n"
        "                        return i\n"
        "                except Exception:\n"
        "                    pass\n"
    )
    tag = detect_deep_nesting(_first_func(source))
    assert tag is not None
    assert "5 levels deep" in tag.detail


def test_with_block_contributes_depth() -> None:
    """`with` is a nesting statement; 4 nested withs must trigger."""
    source = (
        "def f(a, b, c, d):\n"
        "    with a:\n"
        "        with b:\n"
        "            with c:\n"
        "                with d:\n"
        "                    return 1\n"
    )
    assert detect_deep_nesting(_first_func(source)) is not None


def test_try_handlers_count() -> None:
    """`except` body is nesting-equivalent to the try body."""
    source = (
        "def f(x):\n"
        "    try:\n"
        "        if x:\n"
        "            for i in x:\n"
        "                if i:\n"
        "                    return i\n"
        "    except Exception:\n"
        "        pass\n"
    )
    # try (1) → if (2) → for (3) → if (4) → return at 4.
    tag = detect_deep_nesting(_first_func(source))
    assert tag is not None
    assert "4 levels deep" in tag.detail


# ---------------------------------------------------------------------------
# Boundary / separation
# ---------------------------------------------------------------------------


def test_nested_function_body_not_counted_for_outer() -> None:
    """A nested `def` defines a separate scope — its nesting is not outer's."""
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        if a:\n"
        "            if b:\n"
        "                if c:\n"
        "                    if d:\n"
        "                        return 1\n"
    )
    # Outer's own nesting depth is 0 (just a def statement at top-level body).
    assert detect_deep_nesting(_first_func(source)) is None


def test_custom_threshold_lower_triggers_sooner() -> None:
    """Threshold is a parameter — a two-deep function flags at threshold 2."""
    source = "def f(a, b):\n    if a:\n        if b:\n            return 1\n"
    func = _first_func(source)
    assert detect_deep_nesting(func, threshold=2) is not None
    assert detect_deep_nesting(func, threshold=3) is None


def test_default_threshold_matches_draft() -> None:
    """Default must match AST_TAGS_DRAFT.md."""
    assert DEFAULT_DEEP_NESTING_THRESHOLD == 4


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


def test_async_function_supported() -> None:
    source = (
        "async def f(a, b, c, d):\n"
        "    if a:\n"
        "        if b:\n"
        "            if c:\n"
        "                if d:\n"
        "                    return 1\n"
    )
    func = _first_func(source)
    assert isinstance(func, ast.AsyncFunctionDef)
    assert detect_deep_nesting(func) is not None


# ---------------------------------------------------------------------------
# Line/col reporting
# ---------------------------------------------------------------------------


def test_tag_reports_line_of_deepest_point() -> None:
    """The reported line should point near the deepest nested statement."""
    source = (
        "def f(a, b, c, d):\n"
        "    if a:\n"
        "        if b:\n"
        "            if c:\n"
        "                if d:\n"
        "                    return 1\n"  # line 6 in fixture
    )
    tag = detect_deep_nesting(_first_func(source))
    assert tag is not None
    # `return 1` is on line 6 inside the innermost body at depth 4.
    assert tag.line == 6


# ---------------------------------------------------------------------------
# Parameterized sweep over threshold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("threshold,expected", [(1, True), (2, True), (3, False), (4, False)])
def test_two_deep_under_various_thresholds(threshold: int, expected: bool) -> None:
    source = "def f(a, b):\n    if a:\n        if b:\n            return 1\n"
    tag = detect_deep_nesting(_first_func(source), threshold=threshold)
    assert (tag is not None) is expected
