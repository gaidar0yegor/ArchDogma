"""Unit tests for the dynamic-magic detector."""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import detect_dynamic_magic


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


# ---------------------------------------------------------------------------
# Clean functions — no tag
# ---------------------------------------------------------------------------


def test_empty_no_tag() -> None:
    func = _first_func("def f():\n    pass\n")
    assert detect_dynamic_magic(func) is None


def test_plain_attribute_access_no_tag() -> None:
    """Regular attribute access via dot is not dynamic-magic."""
    source = "def f(obj):\n    return obj.name\n"
    assert detect_dynamic_magic(_first_func(source)) is None


def test_builtin_qualified_not_caught() -> None:
    """builtins.eval(...) is not caught in v0.1 — documented limitation."""
    source = "def f(x):\n    import builtins\n    return builtins.eval(x)\n"
    assert detect_dynamic_magic(_first_func(source)) is None


# ---------------------------------------------------------------------------
# Each covered builtin
# ---------------------------------------------------------------------------


def test_getattr_triggers() -> None:
    source = "def f(obj, name):\n    return getattr(obj, name)\n"
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert tag.name == "dynamic-magic"
    assert "getattr" in tag.detail


def test_setattr_triggers() -> None:
    source = "def f(obj, name, val):\n    setattr(obj, name, val)\n"
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert "setattr" in tag.detail


def test_delattr_triggers() -> None:
    source = "def f(obj, name):\n    delattr(obj, name)\n"
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert "delattr" in tag.detail


def test_eval_triggers() -> None:
    source = "def f(s):\n    return eval(s)\n"
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert "eval" in tag.detail


def test_exec_triggers() -> None:
    source = "def f(code):\n    exec(code)\n"
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert "exec" in tag.detail


def test_dunder_import_triggers() -> None:
    source = "def f(name):\n    return __import__(name)\n"
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert "__import__" in tag.detail


# ---------------------------------------------------------------------------
# Multiple and mixed occurrences
# ---------------------------------------------------------------------------


def test_multiple_calls_reported() -> None:
    source = (
        "def f(obj, code):\n"
        "    x = getattr(obj, 'x')\n"
        "    exec(code)\n"
        "    return x\n"
    )
    tag = detect_dynamic_magic(_first_func(source))
    assert tag is not None
    assert "2" in tag.detail
    assert "exec" in tag.detail
    assert "getattr" in tag.detail


# ---------------------------------------------------------------------------
# Scope boundary
# ---------------------------------------------------------------------------


def test_inner_function_not_counted() -> None:
    """Dynamic builtins inside a nested def are not attributed to the outer function."""
    source = (
        "def outer():\n"
        "    def inner(obj):\n"
        "        return getattr(obj, 'x')\n"
        "    return inner\n"
    )
    assert detect_dynamic_magic(_first_func(source)) is None
