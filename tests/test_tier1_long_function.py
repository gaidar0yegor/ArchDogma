"""Unit tests for the long-function detector.

SLOC = set of physical lines that contain ≥1 AST statement node, excluding:
  - blanks
  - comment-only lines
  - the initial docstring
  - bodies of nested def / async def / class (only signature line counts)
"""

from __future__ import annotations

import ast

import pytest

from archdogma.probe.tags.tier1 import (
    DEFAULT_LONG_FUNCTION_LOC,
    Tag,
    detect_long_function,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef), (
        f"fixture must start with def/async def, got {type(node).__name__}"
    )
    return node


def _make_body(n_stmts: int) -> str:
    """Build a function body with exactly `n_stmts` one-line statements."""
    lines = "\n".join(f"    x_{i} = {i}" for i in range(n_stmts))
    return f"def f():\n{lines}\n"


# ---------------------------------------------------------------------------
# Below threshold
# ---------------------------------------------------------------------------


def test_empty_body_no_tag() -> None:
    """A single `pass` — 1 SLOC, far below any reasonable threshold."""
    func = _first_func("def f():\n    pass\n")
    assert detect_long_function(func) is None


def test_one_statement_no_tag() -> None:
    func = _first_func(_make_body(1))
    assert detect_long_function(func) is None


def test_just_below_default_threshold() -> None:
    """79 statements → below default 80, no tag."""
    func = _first_func(_make_body(79))
    assert detect_long_function(func) is None


# ---------------------------------------------------------------------------
# At / above threshold
# ---------------------------------------------------------------------------


def test_at_default_threshold_triggers() -> None:
    """Exactly 80 statements → meets default threshold."""
    func = _first_func(_make_body(80))
    tag = detect_long_function(func)
    assert isinstance(tag, Tag)
    assert tag.name == "long-function"
    assert "80 SLOC" in tag.detail


def test_above_threshold_reports_correct_count() -> None:
    func = _first_func(_make_body(150))
    tag = detect_long_function(func)
    assert tag is not None
    assert "150 SLOC" in tag.detail


def test_default_threshold_matches_draft() -> None:
    """AST_TAGS_DRAFT.md pins the default at 80."""
    assert DEFAULT_LONG_FUNCTION_LOC == 80


# ---------------------------------------------------------------------------
# The whole point: blanks / comments / docstrings don't inflate
# ---------------------------------------------------------------------------


def test_blank_lines_not_counted() -> None:
    """80 physical lines but half are blanks → 40 SLOC → no tag."""
    body = "\n".join(f"    x_{i} = {i}\n" for i in range(40))  # double-newlines = blanks
    func = _first_func(f"def f():\n{body}\n")
    assert detect_long_function(func, threshold=50) is None  # 40 < 50


def test_comments_not_counted() -> None:
    """Dense comments between statements don't count as SLOC."""
    body_lines = []
    for i in range(30):
        body_lines.append(f"    # comment about x_{i}")
        body_lines.append(f"    x_{i} = {i}")
    source = "def f():\n" + "\n".join(body_lines) + "\n"
    func = _first_func(source)
    # 60 physical lines (30 comments + 30 stmts), but 30 SLOC.
    tag = detect_long_function(func, threshold=40)
    assert tag is None  # 30 < 40
    tag2 = detect_long_function(func, threshold=30)
    assert tag2 is not None
    assert "30 SLOC" in tag2.detail


def test_docstring_not_counted() -> None:
    """A multi-line docstring doesn't contribute to SLOC."""
    source = (
        "def f():\n"
        '    """Doc line one.\n'
        "\n"
        "    Doc line two.\n"
        "    Doc line three.\n"
        "    Doc line four.\n"
        '    """\n'
        "    x = 1\n"
    )
    func = _first_func(source)
    # The function covers lines 1-8 but only `x = 1` is a non-docstring stmt.
    tag = detect_long_function(func, threshold=2)
    assert tag is None  # 1 SLOC < 2


def test_bare_string_inside_body_is_not_a_docstring() -> None:
    """Only the FIRST statement is a docstring. A later bare string counts."""
    source = (
        "def f():\n"
        "    x = 1\n"
        '    "not a docstring — just a dead-code string expr"\n'
        "    y = 2\n"
    )
    func = _first_func(source)
    tag = detect_long_function(func, threshold=3)
    assert tag is not None  # 3 SLOC: x=1, bare-string, y=2
    assert "3 SLOC" in tag.detail


# ---------------------------------------------------------------------------
# Multi-line statements
# ---------------------------------------------------------------------------


def test_multi_line_statement_counts_each_physical_line() -> None:
    """A statement spanning 4 lines counts as 4 SLOC."""
    source = (
        "def f():\n"
        "    x = (\n"
        "        1\n"
        "        + 2\n"
        "    )\n"
    )
    func = _first_func(source)
    tag = detect_long_function(func, threshold=4)
    assert tag is not None  # 4 SLOC: the assignment spans lines 2-5
    assert "4 SLOC" in tag.detail


# ---------------------------------------------------------------------------
# Control flow — every stmt's physical lines count, deduplicated
# ---------------------------------------------------------------------------


def test_control_flow_counted_correctly() -> None:
    """if/for/while bodies contribute their physical lines (once each)."""
    source = (
        "def f(x):\n"
        "    if x:\n"
        "        a = 1\n"
        "        b = 2\n"
        "    else:\n"
        "        c = 3\n"
        "    for i in range(10):\n"
        "        d = i\n"
    )
    func = _first_func(source)
    # The outer `if` statement's span (lineno→end_lineno) covers lines 2–6
    # INCLUDING the `else:` keyword line (5) — it's part of the If structure.
    # Plus the `for` statement covers lines 7–8. Union: {2,3,4,5,6,7,8} = 7 SLOC.
    tag = detect_long_function(func, threshold=7)
    assert tag is not None
    assert "7 SLOC" in tag.detail
    assert detect_long_function(func, threshold=8) is None


# ---------------------------------------------------------------------------
# Scope boundary — nested def / class
# ---------------------------------------------------------------------------


def test_nested_def_body_not_counted_for_outer() -> None:
    """A nested `def`'s body belongs to the inner scope. Outer counts only
    the `def inner` signature line (plus its own other statements)."""
    source = (
        "def outer():\n"
        "    x = 1\n"
        "    def inner():\n"
        "        a = 1\n"
        "        b = 2\n"
        "        c = 3\n"
        "        d = 4\n"
        "        e = 5\n"
        "    y = 2\n"
    )
    func = _first_func(source)
    # Outer SLOC: x=1 (line 2), `def inner` (line 3), y=2 (line 9) → 3.
    # The 5 lines inside inner (4-8) are in inner's scope.
    tag = detect_long_function(func, threshold=3)
    assert tag is not None
    assert "3 SLOC" in tag.detail


def test_nested_class_body_not_counted() -> None:
    source = (
        "def outer():\n"
        "    x = 1\n"
        "    class C:\n"
        "        a = 1\n"
        "        b = 2\n"
        "    y = 2\n"
    )
    func = _first_func(source)
    # Outer SLOC: x=1, `class C`, y=2 → 3.
    tag = detect_long_function(func, threshold=3)
    assert tag is not None
    assert "3 SLOC" in tag.detail


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


def test_async_function_supported() -> None:
    func = _first_func("async def f():\n" + "\n".join(f"    x_{i} = {i}" for i in range(80)) + "\n")
    assert isinstance(func, ast.AsyncFunctionDef)
    assert detect_long_function(func) is not None


# ---------------------------------------------------------------------------
# Custom threshold
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stmts,threshold,expected",
    [
        (10, 20, False),
        (19, 20, False),
        (20, 20, True),
        (21, 20, True),
        (1000, 80, True),
    ],
)
def test_threshold_parameter_honored(stmts: int, threshold: int, expected: bool) -> None:
    func = _first_func(_make_body(stmts))
    tag = detect_long_function(func, threshold=threshold)
    assert (tag is not None) is expected


# ---------------------------------------------------------------------------
# Tag shape
# ---------------------------------------------------------------------------


def test_tag_points_at_function_signature() -> None:
    """The tag's line/col identify the function, not any inner statement."""
    func = _first_func(_make_body(100))
    tag = detect_long_function(func)
    assert tag is not None
    assert tag.line == func.lineno
    assert tag.col == func.col_offset


def test_tag_detail_mentions_honest_source_note() -> None:
    """Detail text must carry the caveat — no research-backed threshold."""
    func = _first_func(_make_body(80))
    tag = detect_long_function(func)
    assert tag is not None
    assert "no research-backed absolute threshold" in tag.detail
