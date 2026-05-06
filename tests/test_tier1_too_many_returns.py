"""Unit tests for the too-many-returns detector.

Counts `return` statements anywhere in the function body, recursing into
control-flow branches but stopping at nested def / async def / class
boundaries (those returns belong to a different function).

Default threshold is 4 — more conservative than pylint R0911 (which uses
6). No research-backed threshold exists; this is honestly a heuristic.
"""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    DEFAULT_TOO_MANY_RETURNS,
    TIER1_DETECTORS,
    Tag,
    detect_too_many_returns,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


# ---------------------------------------------------------------------------
# Default threshold + registry contract
# ---------------------------------------------------------------------------


def test_default_threshold_is_four() -> None:
    assert DEFAULT_TOO_MANY_RETURNS == 4


def test_registered_in_tier1_registry() -> None:
    names = [name for name, _ in TIER1_DETECTORS]
    assert "too-many-returns" in names


# ---------------------------------------------------------------------------
# Threshold boundary cases
# ---------------------------------------------------------------------------


def test_no_returns_no_tag() -> None:
    func = _first_func("def f():\n    pass\n")
    assert detect_too_many_returns(func) is None


def test_below_threshold_no_tag() -> None:
    """3 returns, default threshold 4 — no tag."""
    func = _first_func(
        "def f(x):\n"
        "    if x == 0:\n"
        "        return 'a'\n"
        "    if x == 1:\n"
        "        return 'b'\n"
        "    return 'c'\n"
    )
    assert detect_too_many_returns(func) is None


def test_at_threshold_triggers() -> None:
    """4 returns at default threshold 4 — triggers."""
    func = _first_func(
        "def f(x):\n"
        "    if x == 0:\n"
        "        return 'a'\n"
        "    if x == 1:\n"
        "        return 'b'\n"
        "    if x == 2:\n"
        "        return 'c'\n"
        "    return 'd'\n"
    )
    tag = detect_too_many_returns(func)
    assert isinstance(tag, Tag)
    assert tag.name == "too-many-returns"


def test_custom_threshold() -> None:
    func = _first_func(
        "def f(x):\n"
        "    if x:\n"
        "        return 1\n"
        "    return 0\n"
    )
    # 2 returns, threshold=2 — triggers.
    assert detect_too_many_returns(func, threshold=2) is not None
    # 2 returns, threshold=3 — does not.
    assert detect_too_many_returns(func, threshold=3) is None


# ---------------------------------------------------------------------------
# Scope rules — nested def's returns are the inner function's
# ---------------------------------------------------------------------------


def test_nested_function_returns_not_counted() -> None:
    """Returns inside a nested def belong to that inner function and must
    NOT count toward the outer function's return total."""
    func = _first_func(
        "def f():\n"
        "    def inner():\n"
        "        if True:\n"
        "            return 1\n"
        "        if False:\n"
        "            return 2\n"
        "        if True:\n"
        "            return 3\n"
        "        return 4\n"
        "    return inner\n"
    )
    # Outer f has exactly 1 return (the last one) — well below threshold.
    assert detect_too_many_returns(func) is None


def test_returns_in_branches_counted() -> None:
    """Returns scattered across if / for / try branches all belong to the
    same scope — they must all be counted."""
    func = _first_func(
        "def f(items):\n"
        "    for it in items:\n"
        "        if it == 1:\n"
        "            return 'a'\n"
        "    try:\n"
        "        return 'b'\n"
        "    except ValueError:\n"
        "        return 'c'\n"
        "    if items:\n"
        "        return 'd'\n"
        "    return 'e'\n"
    )
    tag = detect_too_many_returns(func)
    assert tag is not None
    assert "5 return statements" in tag.detail


# ---------------------------------------------------------------------------
# Tag shape
# ---------------------------------------------------------------------------


def test_tag_name_is_too_many_returns() -> None:
    func = _first_func(
        "def f(x):\n"
        "    if x == 0:\n"
        "        return 'a'\n"
        "    if x == 1:\n"
        "        return 'b'\n"
        "    if x == 2:\n"
        "        return 'c'\n"
        "    return 'd'\n"
    )
    tag = detect_too_many_returns(func)
    assert tag is not None
    assert tag.name == "too-many-returns"


def test_detail_contains_count() -> None:
    func = _first_func(
        "def f(x):\n"
        "    if x == 0:\n"
        "        return 0\n"
        "    if x == 1:\n"
        "        return 1\n"
        "    if x == 2:\n"
        "        return 2\n"
        "    if x == 3:\n"
        "        return 3\n"
        "    return -1\n"
    )
    tag = detect_too_many_returns(func)
    assert tag is not None
    assert "5 return statements" in tag.detail
