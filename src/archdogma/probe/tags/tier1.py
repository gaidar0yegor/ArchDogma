"""Tier 1 tag detectors — single-file AST, no cross-file graph, no git, no coverage.

v0.1 target set (see AST_TAGS_DRAFT.md):
    - deep-nesting           ← implemented
    - long-function          ← pending
    - god-function           ← pending
    - god-class              ← pending
    - deep-inheritance       ← pending (single-file slice)
    - if-on-parameter        ← pending

All thresholds are defaults per AST_TAGS_DRAFT.md and are configurable.
No threshold is treated as research-proven unless explicitly cited in the draft.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

# Defaults. Override via CLI / config in later milestones.
DEFAULT_DEEP_NESTING_THRESHOLD = 4
DEFAULT_LONG_FUNCTION_LOC = 80
DEFAULT_GOD_FUNCTION_LOC = 200
DEFAULT_GOD_FUNCTION_BRANCHES = 15
DEFAULT_GOD_CLASS_LOC = 500
DEFAULT_GOD_CLASS_METHODS = 25
DEFAULT_DEEP_INHERITANCE_DEPTH = 4
DEFAULT_IF_ON_PARAMETER_BRANCHES = 3


@dataclass(frozen=True)
class Tag:
    """A signal raised by a Tier 1 detector.

    `name` is a short, stable kebab-case identifier (also used as the key for
    catalog lookup once ADR-002 lands).
    `detail` is a short human-readable explanation of what triggered the tag.
    `line`, `col` point to the most representative location in the source.
    """

    name: str
    detail: str
    line: int
    col: int


# ---------------------------------------------------------------------------
# deep-nesting
# ---------------------------------------------------------------------------
#
# Counts the maximum depth of control-flow nesting inside a function body.
#
# Nesting statements: if / for / async for / while / with / async with / try /
# match. An elif clause does NOT add depth — the Python AST parses elif as a
# single-If inside the parent If's `orelse`, and we flatten that case so the
# reported depth matches how a human reads the code.
#
# Function and class definitions nested inside the probed function are NOT
# descended into — they are separate scopes and are probed separately.
#
# List/dict/set comprehensions are expressions, not statements, and are not
# measured by this v0.1 detector. Deeply nested comprehensions remain a known
# gap; see AST_TAGS_DRAFT.md.


_SIMPLE_NESTING = (ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith)


def _walk_nesting(
    stmts: list[ast.stmt], current_depth: int, state: dict[str, int]
) -> None:
    """Record max depth reached across `stmts`, descending into nesting ones."""
    for s in stmts:
        # Every statement visited contributes its current depth.
        if current_depth > state["max_depth"]:
            state["max_depth"] = current_depth
            state["line"] = s.lineno
            state["col"] = s.col_offset

        if isinstance(s, ast.If):
            _walk_nesting(s.body, current_depth + 1, state)
            # elif handling: a lone If in orelse means `elif`, so do not add
            # another level — recurse at the SAME depth as the parent If.
            if len(s.orelse) == 1 and isinstance(s.orelse[0], ast.If):
                _walk_nesting([s.orelse[0]], current_depth, state)
            else:
                _walk_nesting(s.orelse, current_depth + 1, state)
        elif isinstance(s, _SIMPLE_NESTING):
            _walk_nesting(s.body, current_depth + 1, state)
            # for / while both carry an orelse clause in Python.
            orelse = getattr(s, "orelse", None)
            if orelse:
                _walk_nesting(orelse, current_depth + 1, state)
        elif isinstance(s, ast.Try):
            _walk_nesting(s.body, current_depth + 1, state)
            for handler in s.handlers:
                _walk_nesting(handler.body, current_depth + 1, state)
            _walk_nesting(s.orelse, current_depth + 1, state)
            _walk_nesting(s.finalbody, current_depth + 1, state)
        elif isinstance(s, ast.Match):
            for case in s.cases:
                _walk_nesting(case.body, current_depth + 1, state)
        # FunctionDef / AsyncFunctionDef / ClassDef inside the body: not
        # descended. They are separate scopes.


def detect_deep_nesting(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    threshold: int = DEFAULT_DEEP_NESTING_THRESHOLD,
) -> Tag | None:
    """Return a `Tag` if the function's nesting depth meets/exceeds `threshold`.

    Depth convention:
        depth 0 = statement at the function's top level
        depth 1 = one level inside an if / for / while / try / with / match
        ...
    """
    state: dict[str, int] = {
        "max_depth": 0,
        "line": func.lineno,
        "col": func.col_offset,
    }
    _walk_nesting(func.body, current_depth=0, state=state)

    if state["max_depth"] < threshold:
        return None

    return Tag(
        name="deep-nesting",
        detail=(
            f"Control flow nested {state['max_depth']} levels deep. "
            f"Default threshold: {threshold}. "
            f"Source note: Cognitive Complexity (Sonarsource 2017) weights "
            f"nesting; no research-backed absolute threshold exists."
        ),
        line=state["line"],
        col=state["col"],
    )


# ---------------------------------------------------------------------------
# long-function
# ---------------------------------------------------------------------------
#
# Counts "source lines of code" (SLOC) inside a function body — lines that
# contain at least one AST statement node. This naturally excludes:
#
#   - blank lines       (no statement lives there)
#   - comment-only lines (not in the AST at all)
#   - the initial docstring (a bare string Expr in position 0 — skipped)
#
# It includes every physical line covered by a statement, so multi-line
# expressions correctly count as N lines. Bodies of nested def / async def /
# class defs inside the probed function are NOT counted — only their signature
# line contributes ("we saw a nested def here"), matching deep-nesting's
# scope-boundary behavior.
#
# This is `long-function` from AST_TAGS_DRAFT.md §Tier 1. Threshold 80 is a
# straight default, honestly not research-backed — the draft flags this.


def _is_docstring(node: ast.stmt) -> bool:
    """Return True if `node` is a bare string expression used as a docstring."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _collect_stmt_lines(
    stmts: list[ast.stmt],
    lines_out: set[int],
    skip_first_docstring: bool = False,
) -> None:
    """Record line numbers covered by each statement in `stmts` (recursive).

    Nested function / class definitions contribute only their own `lineno`
    (the `def` / `class` keyword line). Their bodies belong to a different
    scope and are probed separately.
    """
    for i, s in enumerate(stmts):
        if skip_first_docstring and i == 0 and _is_docstring(s):
            continue

        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            # Count just the signature line; do not descend into inner scope.
            lines_out.add(s.lineno)
            continue

        end = s.end_lineno or s.lineno
        lines_out.update(range(s.lineno, end + 1))

        # Recurse into sub-bodies that are part of the same scope.
        for attr in ("body", "orelse", "finalbody"):
            sub = getattr(s, attr, None)
            if sub:
                _collect_stmt_lines(sub, lines_out, False)
        if isinstance(s, ast.Try):
            for handler in s.handlers:
                _collect_stmt_lines(handler.body, lines_out, False)
        if isinstance(s, ast.Match):
            for case in s.cases:
                _collect_stmt_lines(case.body, lines_out, False)


def detect_long_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    threshold: int = DEFAULT_LONG_FUNCTION_LOC,
) -> Tag | None:
    """Return a `Tag` if the function body has `threshold` SLOC or more.

    SLOC = lines containing ≥1 AST statement. Does not count blanks,
    comment-only lines, the initial docstring, or nested-scope bodies.
    """
    lines: set[int] = set()
    _collect_stmt_lines(func.body, lines, skip_first_docstring=True)

    sloc = len(lines)
    if sloc < threshold:
        return None

    return Tag(
        name="long-function",
        detail=(
            f"Function body has {sloc} SLOC (excluding blanks, comments, "
            f"docstring, and nested-scope bodies). "
            f"Default threshold: {threshold}. "
            f"Source note: no research-backed absolute threshold — 50/80/100 "
            f"heuristics vary by style guide."
        ),
        line=func.lineno,
        col=func.col_offset,
    )


# ---------------------------------------------------------------------------
# Registry of Tier 1 detectors
# ---------------------------------------------------------------------------
#
# Each entry is (tag-name, callable). Callables take an ast.FunctionDef /
# AsyncFunctionDef and return a Tag | None. This is the v0.1 registration
# surface used by `walker.probe_function`.

TIER1_DETECTORS: tuple[
    tuple[str, "object"], ...
] = (
    ("deep-nesting", detect_deep_nesting),
    ("long-function", detect_long_function),
)
