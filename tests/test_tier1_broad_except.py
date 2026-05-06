"""Unit tests for the broad-except detector.

Signal = any occurrence of `except:`, `except Exception:`, or
`except BaseException:` inside the function body, recursing into nested
try/for/while/with/match scopes but stopping at nested def/class
boundaries.

Specific exception types (`except ValueError:`) and attribute-qualified
types (`except module.Exception:`) are NOT caught — the latter is a known
v0.1 gap (cross-scope name resolution is Tier 2).
"""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    TIER1_DETECTORS,
    Tag,
    detect_broad_except,
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
    assert "broad-except" in names


# ---------------------------------------------------------------------------
# No-trigger cases
# ---------------------------------------------------------------------------


def test_no_try_no_tag() -> None:
    func = _first_func("def f():\n    return 1\n")
    assert detect_broad_except(func) is None


def test_specific_except_no_tag() -> None:
    func = _first_func(
        "def f():\n"
        "    try:\n"
        "        x = 1\n"
        "    except ValueError:\n"
        "        x = 0\n"
    )
    assert detect_broad_except(func) is None


# ---------------------------------------------------------------------------
# Trigger cases — bare / Exception / BaseException
# ---------------------------------------------------------------------------


def test_bare_except_triggers() -> None:
    func = _first_func(
        "def f():\n"
        "    try:\n"
        "        x = 1\n"
        "    except:\n"
        "        x = 0\n"
    )
    tag = detect_broad_except(func)
    assert isinstance(tag, Tag)
    assert tag.name == "broad-except"
    assert "bare except" in tag.detail


def test_except_exception_triggers() -> None:
    func = _first_func(
        "def f():\n"
        "    try:\n"
        "        x = 1\n"
        "    except Exception:\n"
        "        x = 0\n"
    )
    tag = detect_broad_except(func)
    assert tag is not None
    assert "Exception" in tag.detail


def test_except_baseexception_triggers() -> None:
    func = _first_func(
        "def f():\n"
        "    try:\n"
        "        x = 1\n"
        "    except BaseException:\n"
        "        x = 0\n"
    )
    tag = detect_broad_except(func)
    assert tag is not None
    assert "BaseException" in tag.detail


# ---------------------------------------------------------------------------
# Scope rules — nested try is in scope; nested def is not
# ---------------------------------------------------------------------------


def test_nested_try_caught() -> None:
    """A broad except inside a for-loop's body is still in the function's
    scope, so it must be caught."""
    func = _first_func(
        "def f(items):\n"
        "    for it in items:\n"
        "        try:\n"
        "            handle(it)\n"
        "        except Exception:\n"
        "            pass\n"
    )
    tag = detect_broad_except(func)
    assert tag is not None


def test_inner_function_not_caught() -> None:
    """A broad except sitting inside a nested def belongs to a different
    scope. Probing the outer function alone must NOT see it."""
    func = _first_func(
        "def f():\n"
        "    def inner():\n"
        "        try:\n"
        "            x = 1\n"
        "        except Exception:\n"
        "            x = 0\n"
        "    inner()\n"
    )
    assert detect_broad_except(func) is None


# ---------------------------------------------------------------------------
# Multiple-handler accounting
# ---------------------------------------------------------------------------


def test_multiple_broad_handlers_count() -> None:
    """Two broad handlers in the same function — count is 2."""
    func = _first_func(
        "def f():\n"
        "    try:\n"
        "        x = 1\n"
        "    except Exception:\n"
        "        x = 0\n"
        "    try:\n"
        "        y = 1\n"
        "    except:\n"
        "        y = 0\n"
    )
    tag = detect_broad_except(func)
    assert tag is not None
    assert "2 broad exception handler(s)" in tag.detail


# ---------------------------------------------------------------------------
# Tag shape
# ---------------------------------------------------------------------------


def test_tag_name_is_broad_except() -> None:
    func = _first_func(
        "def f():\n"
        "    try:\n"
        "        x = 1\n"
        "    except Exception:\n"
        "        x = 0\n"
    )
    tag = detect_broad_except(func)
    assert tag is not None
    assert tag.name == "broad-except"
