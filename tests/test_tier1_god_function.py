"""Unit tests for the god-function detector.

Signal = SLOC ≥ loc_threshold AND branches ≥ branch_threshold.
Both must trip; either alone is a different shape of smell.

Branches: if / elif / for / while / except / case.
`with` is NOT a branch (sequential). Boolean ops (and/or) are NOT counted.
"""

from __future__ import annotations

import ast

import pytest

from archdogma.probe.tags.tier1 import (
    DEFAULT_GOD_FUNCTION_BRANCHES,
    DEFAULT_GOD_FUNCTION_LOC,
    Tag,
    detect_god_function,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


def _gen_function(sloc: int, n_ifs: int) -> str:
    """Build a function with ~sloc plain statements and `n_ifs` if/else pairs.

    Each `if` contributes 1 branch. `else` does not — it's the absence of a
    branch. Each if block also adds 3 SLOC (`if` line + body + else line +
    else body → set of ~4 lines). We pad out with plain assignments to hit
    the SLOC target.
    """
    lines: list[str] = []
    for i in range(n_ifs):
        lines.append(f"    if cond_{i}:")
        lines.append(f"        a_{i} = {i}")
        lines.append("    else:")
        lines.append(f"        a_{i} = -{i}")
    pad = sloc - len(lines)
    for i in range(max(0, pad)):
        lines.append(f"    pad_{i} = {i}")
    body = "\n".join(lines) or "    pass"
    return f"def f():\n{body}\n"


# ---------------------------------------------------------------------------
# Default thresholds pin what AST_TAGS_DRAFT.md and ADR registry expect
# ---------------------------------------------------------------------------


def test_defaults_match_registry() -> None:
    assert DEFAULT_GOD_FUNCTION_LOC == 200
    assert DEFAULT_GOD_FUNCTION_BRANCHES == 15


# ---------------------------------------------------------------------------
# Four quadrants (short/long × few-branches/many-branches)
# ---------------------------------------------------------------------------


def test_short_and_linear_no_tag() -> None:
    func = _first_func("def f():\n    x = 1\n    y = 2\n    return x + y\n")
    assert detect_god_function(func) is None


def test_long_but_linear_no_tag() -> None:
    """300 SLOC, 0 branches — not a god-function. Just a long one."""
    func = _first_func(_gen_function(sloc=300, n_ifs=0))
    assert detect_god_function(func) is None


def test_short_but_branchy_no_tag() -> None:
    """A 30-branch dispatcher in 90 SLOC is NOT god-function at default
    thresholds (200 SLOC required)."""
    func = _first_func(_gen_function(sloc=90, n_ifs=20))
    assert detect_god_function(func) is None


def test_long_and_branchy_triggers() -> None:
    func = _first_func(_gen_function(sloc=220, n_ifs=16))
    tag = detect_god_function(func)
    assert isinstance(tag, Tag)
    assert tag.name == "god-function"
    assert "220 SLOC" in tag.detail
    assert "16 branches" in tag.detail


# ---------------------------------------------------------------------------
# Threshold knobs (AND of two thresholds)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sloc,branches,loc_t,br_t,expected",
    [
        (100, 20, 50, 10, True),    # both met
        (20, 5, 50, 3, False),      # SLOC short (20 < 50) — 5 ifs×4 lines = 20 SLOC
        (100, 9, 50, 10, False),    # branches short
        (50, 10, 50, 10, True),     # both at boundary
    ],
)
def test_threshold_and_semantics(
    sloc: int, branches: int, loc_t: int, br_t: int, expected: bool
) -> None:
    func = _first_func(_gen_function(sloc=sloc, n_ifs=branches))
    tag = detect_god_function(func, loc_threshold=loc_t, branch_threshold=br_t)
    assert (tag is not None) is expected


# ---------------------------------------------------------------------------
# Branch counting details — what counts, what doesn't
# ---------------------------------------------------------------------------


def test_elif_counted_as_branches() -> None:
    """Each elif is an independent branch (Python parses it as nested If).
    The test uses a very low threshold so only the branch count matters."""
    source = (
        "def f():\n"
        "    if a:\n"
        "        x = 1\n"
        "    elif b:\n"
        "        x = 2\n"
        "    elif c:\n"
        "        x = 3\n"
        "    else:\n"
        "        x = 4\n"
    )
    func = _first_func(source)
    # 1 if + 2 elif = 3 branches. SLOC ≈ 8.
    tag = detect_god_function(func, loc_threshold=3, branch_threshold=3)
    assert tag is not None
    assert "3 branches" in tag.detail


def test_for_and_while_counted() -> None:
    source = (
        "def f():\n"
        "    for i in range(10):\n"
        "        while i:\n"
        "            i -= 1\n"
    )
    func = _first_func(source)
    # 1 for + 1 while = 2 branches.
    tag = detect_god_function(func, loc_threshold=1, branch_threshold=2)
    assert tag is not None
    assert "2 branches" in tag.detail


def test_with_not_counted_as_branch() -> None:
    """`with` is sequential, not branching."""
    source = (
        "def f():\n"
        "    with open('x') as a:\n"
        "        a.read()\n"
        "    with open('y') as b:\n"
        "        b.read()\n"
    )
    func = _first_func(source)
    # 0 branches. Should NOT trip with branch_threshold=1.
    assert detect_god_function(func, loc_threshold=1, branch_threshold=1) is None


def test_except_handlers_counted_each() -> None:
    source = (
        "def f():\n"
        "    try:\n"
        "        a = 1\n"
        "    except ValueError:\n"
        "        a = -1\n"
        "    except KeyError:\n"
        "        a = -2\n"
    )
    func = _first_func(source)
    # try block itself: 0. Two except handlers: 2 branches.
    tag = detect_god_function(func, loc_threshold=1, branch_threshold=2)
    assert tag is not None
    assert "2 branches" in tag.detail


def test_match_cases_counted_each() -> None:
    source = (
        "def f(x):\n"
        "    match x:\n"
        "        case 1:\n"
        "            y = 'one'\n"
        "        case 2:\n"
        "            y = 'two'\n"
        "        case _:\n"
        "            y = 'other'\n"
    )
    func = _first_func(source)
    # 3 case clauses = 3 branches.
    tag = detect_god_function(func, loc_threshold=1, branch_threshold=3)
    assert tag is not None
    assert "3 branches" in tag.detail


def test_nested_def_branches_not_counted_for_outer() -> None:
    """Scope boundary: `if`s inside a nested def are that def's problem."""
    source = (
        "def outer():\n"
        "    if a:\n"
        "        pass\n"
        "    def inner():\n"
        "        if b:\n"
        "            pass\n"
        "        if c:\n"
        "            pass\n"
        "        if d:\n"
        "            pass\n"
    )
    func = _first_func(source)
    # Outer: 1 branch (the `if a`). Inner's 3 are NOT counted.
    tag = detect_god_function(func, loc_threshold=1, branch_threshold=2)
    assert tag is None
    tag2 = detect_god_function(func, loc_threshold=1, branch_threshold=1)
    assert tag2 is not None
    assert "1 branches" in tag2.detail


# ---------------------------------------------------------------------------
# Tag shape — location + honest source note
# ---------------------------------------------------------------------------


def test_tag_points_at_function_signature() -> None:
    func = _first_func(_gen_function(sloc=220, n_ifs=20))
    tag = detect_god_function(func)
    assert tag is not None
    assert tag.line == func.lineno
    assert tag.col == func.col_offset


def test_tag_detail_mentions_honest_source_note() -> None:
    func = _first_func(_gen_function(sloc=220, n_ifs=20))
    tag = detect_god_function(func)
    assert tag is not None
    assert "McCabe" in tag.detail
    assert "no research-backed absolute" in tag.detail
