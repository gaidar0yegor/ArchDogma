"""Unit tests for the magic-numbers detector."""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    DEFAULT_MAGIC_NUMBERS_THRESHOLD,
    detect_magic_numbers,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


# ---------------------------------------------------------------------------
# Excluded values — never trigger
# ---------------------------------------------------------------------------


def test_empty_body_no_tag() -> None:
    func = _first_func("def f():\n    pass\n")
    assert detect_magic_numbers(func) is None


def test_zero_one_excluded() -> None:
    source = (
        "def f(x):\n"
        "    return x + 0 + 1 + 0 + 1 + 0 + 1\n"
    )
    assert detect_magic_numbers(_first_func(source)) is None


def test_negative_one_excluded() -> None:
    source = "def f(lst):\n    return lst[-1]\n"
    # -1 inside a subscript — AST represents as UnaryOp(USub, Constant(1))
    # The inner Constant(1) is excluded (value == 1).
    assert detect_magic_numbers(_first_func(source)) is None


def test_bool_literals_excluded() -> None:
    """True/False must NOT count as magic numbers."""
    source = (
        "def f(x):\n"
        "    a = True\n"
        "    b = False\n"
        "    c = True\n"
        "    d = False\n"
        "    e = True\n"
        "    return a or b or c or d or e\n"
    )
    assert detect_magic_numbers(_first_func(source)) is None


# ---------------------------------------------------------------------------
# Below threshold
# ---------------------------------------------------------------------------


def test_four_magic_numbers_no_tag() -> None:
    source = (
        "def f():\n"
        "    a = 42\n"
        "    b = 100\n"
        "    c = 3.14\n"
        "    d = 7\n"
        "    return a + b + c + d\n"
    )
    assert detect_magic_numbers(_first_func(source)) is None


# ---------------------------------------------------------------------------
# At/above threshold
# ---------------------------------------------------------------------------


def test_five_magic_numbers_triggers() -> None:
    source = (
        "def f():\n"
        "    a = 2\n"
        "    b = 3\n"
        "    c = 4\n"
        "    d = 5\n"
        "    e = 6\n"
        "    return a + b + c + d + e\n"
    )
    tag = detect_magic_numbers(_first_func(source))
    assert tag is not None
    assert tag.name == "magic-numbers"
    assert "5" in tag.detail


def test_float_counts() -> None:
    source = (
        "def f():\n"
        "    return 2.5 + 3.7 + 4.2 + 9.9 + 0.5\n"
    )
    tag = detect_magic_numbers(_first_func(source))
    assert tag is not None


def test_string_literals_not_counted() -> None:
    """String constants must not count toward magic numbers."""
    source = (
        "def f():\n"
        "    a = 'hello'\n"
        "    b = 'world'\n"
        "    c = 'foo'\n"
        "    d = 'bar'\n"
        "    e = 'baz'\n"
        "    f = 2\n"
        "    return a\n"
    )
    # Only one magic number (2) — below threshold
    assert detect_magic_numbers(_first_func(source)) is None


def test_custom_threshold() -> None:
    source = (
        "def f():\n"
        "    return 2 + 3 + 4\n"
    )
    assert detect_magic_numbers(_first_func(source), threshold=2) is not None
    assert detect_magic_numbers(_first_func(source), threshold=4) is None


def test_inner_function_not_counted() -> None:
    """Numeric literals inside a nested def are not counted for the outer function."""
    source = (
        "def outer():\n"
        "    def inner():\n"
        "        return 2 + 3 + 4 + 5 + 6\n"
        "    return inner\n"
    )
    assert detect_magic_numbers(_first_func(source)) is None


def test_repeated_literal_counted_each_time() -> None:
    """Each literal occurrence is counted; same value used twice = 2 occurrences."""
    source = (
        "def f():\n"
        "    return 42 + 42 + 42 + 42 + 42\n"
    )
    tag = detect_magic_numbers(_first_func(source))
    assert tag is not None
    assert "5" in tag.detail
