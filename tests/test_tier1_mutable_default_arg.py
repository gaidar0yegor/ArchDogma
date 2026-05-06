"""Unit tests for the mutable-default-arg detector.

Python evaluates default values once at definition time. Mutable defaults
(list / dict / set literals) are shared across calls — a classic gotcha.

Detector covers list / dict / set LITERALS only; `MyClass()` Call defaults
are out of scope for v0.1 (indistinguishable at the AST from the rare
"frozen factory" pattern). `set()` is a Call, not an `ast.Set`, and is
also not flagged in v0.1 — only set displays like `{1, 2}` trigger.
"""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    TIER1_DETECTORS,
    Tag,
    detect_mutable_default_arg,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------


def test_registered_in_tier1_registry() -> None:
    names = [name for name, _ in TIER1_DETECTORS]
    assert "mutable-default-arg" in names


# ---------------------------------------------------------------------------
# No-trigger cases
# ---------------------------------------------------------------------------


def test_no_defaults_no_tag() -> None:
    func = _first_func("def f():\n    pass\n")
    assert detect_mutable_default_arg(func) is None


def test_immutable_defaults_no_tag() -> None:
    func = _first_func('def f(x=1, y="hello", z=None):\n    pass\n')
    assert detect_mutable_default_arg(func) is None


# ---------------------------------------------------------------------------
# Trigger cases — list / dict / set literals
# ---------------------------------------------------------------------------


def test_list_default_triggers() -> None:
    func = _first_func("def f(x=[]):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert isinstance(tag, Tag)
    assert "list" in tag.detail


def test_dict_default_triggers() -> None:
    func = _first_func("def f(x={}):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert tag is not None
    assert "dict" in tag.detail


def test_set_literal_default_triggers() -> None:
    """`{1, 2}` is `ast.Set` — a set display, which we DO catch.
    `set()` is `ast.Call` — out of scope for v0.1."""
    func = _first_func("def f(x={1, 2}):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert tag is not None
    assert "set" in tag.detail


def test_kwonly_list_default_triggers() -> None:
    func = _first_func("def f(*, x=[]):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert tag is not None
    assert "list" in tag.detail


def test_mixed_one_mutable_triggers() -> None:
    """Only the mutable default counts — but a single one is enough."""
    func = _first_func("def f(a=1, b=[]):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert tag is not None
    assert "'b'" in tag.detail


# ---------------------------------------------------------------------------
# Scope rules — inner def's defaults belong to inner scope
# ---------------------------------------------------------------------------


def test_inner_function_not_counted() -> None:
    """A mutable default on a nested def is the inner function's problem.
    Probing the outer function alone must NOT trigger."""
    func = _first_func(
        "def f():\n"
        "    def inner(x=[]):\n"
        "        return x\n"
        "    return inner\n"
    )
    assert detect_mutable_default_arg(func) is None


# ---------------------------------------------------------------------------
# Tag shape
# ---------------------------------------------------------------------------


def test_tag_name_is_mutable_default_arg() -> None:
    func = _first_func("def f(x=[]):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert tag is not None
    assert tag.name == "mutable-default-arg"


def test_detail_contains_arg_name() -> None:
    func = _first_func("def f(items=[]):\n    pass\n")
    tag = detect_mutable_default_arg(func)
    assert tag is not None
    assert "items" in tag.detail
