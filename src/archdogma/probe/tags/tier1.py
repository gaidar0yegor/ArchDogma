"""Tier 1 tag detectors — single-file AST, no cross-file graph, no git, no coverage.

v0.1 target set (see AST_TAGS_DRAFT.md):
    - deep-nesting           ← implemented
    - long-function          ← implemented
    - god-function           ← implemented
    - too-many-params        ← implemented
    - if-on-parameter        ← implemented
    - magic-numbers          ← implemented
    - dynamic-magic          ← implemented
    - broad-except           ← implemented
    - mutable-default-arg    ← implemented
    - too-many-returns       ← implemented
    - god-class              ← implemented (class-level)
    - deep-inheritance       ← implemented (class-level, single-file slice)

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
DEFAULT_GOD_CLASS_METHODS = 15
DEFAULT_GOD_CLASS_ATTRS = 5
DEFAULT_DEEP_INHERITANCE_DEPTH = 4
DEFAULT_IF_ON_PARAMETER_BRANCHES = 3
DEFAULT_TOO_MANY_PARAMS = 5
DEFAULT_MAGIC_NUMBERS_THRESHOLD = 5
DEFAULT_TOO_MANY_RETURNS = 4
# dynamic-magic, broad-except, mutable-default-arg: binary tags, no threshold


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
# god-function
# ---------------------------------------------------------------------------
#
# Combines two signals from the same AST walk: SLOC (reused from
# long-function) AND a McCabe-ish branch count. A function is "god" only
# when BOTH thresholds trip — long-AND-branchy. Short-but-branchy and
# long-but-linear are different shapes of smell, handled (or not) by other
# detectors.
#
# Branch counting is deliberately conservative:
#   +1 per If / elif         (elif = nested If in orelse — natural recursion)
#   +1 per For / AsyncFor / While
#   +1 per `except` handler
#   +1 per `case` clause in match
#
# We do NOT count boolean operators (and/or) inside test expressions. Classic
# McCabe would; practice varies by tool (radon vs lizard vs Sonar). Skipping
# them keeps the number legible and matches the honest_verdict of
# AST_TAGS_DRAFT.md: the threshold isn't research-backed either way.
#
# Nested def / class inside the function are NOT descended — same scope rule
# as the other Tier 1 detectors.


def _count_branches(stmts: list[ast.stmt], state: dict[str, int]) -> None:
    """Count branch-creating statements in `stmts`, recursively (same scope)."""
    for s in stmts:
        if isinstance(s, ast.If):
            state["n"] += 1
            _count_branches(s.body, state)
            _count_branches(s.orelse, state)
        elif isinstance(s, _SIMPLE_NESTING):
            # For / AsyncFor / While are loops and count; With / AsyncWith
            # are sequential and do not.
            if isinstance(s, ast.For | ast.AsyncFor | ast.While):
                state["n"] += 1
            _count_branches(s.body, state)
            orelse = getattr(s, "orelse", None)
            if orelse:
                _count_branches(orelse, state)
        elif isinstance(s, ast.Try):
            _count_branches(s.body, state)
            for handler in s.handlers:
                state["n"] += 1
                _count_branches(handler.body, state)
            _count_branches(s.orelse, state)
            _count_branches(s.finalbody, state)
        elif isinstance(s, ast.Match):
            for case in s.cases:
                state["n"] += 1
                _count_branches(case.body, state)
        elif isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            # Scope boundary — do not descend.
            continue
        else:
            # Plain statement: descend into sub-bodies that exist in THIS scope.
            for attr in ("body", "orelse", "finalbody"):
                sub = getattr(s, attr, None)
                if sub:
                    _count_branches(sub, state)


def _compute_sloc(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """SLOC of `func` body. Single source of truth — shared with long-function."""
    lines: set[int] = set()
    _collect_stmt_lines(func.body, lines, skip_first_docstring=True)
    return len(lines)


def detect_god_function(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    loc_threshold: int = DEFAULT_GOD_FUNCTION_LOC,
    branch_threshold: int = DEFAULT_GOD_FUNCTION_BRANCHES,
) -> Tag | None:
    """Return a `Tag` if the function is BOTH long AND branchy.

    `loc_threshold` and `branch_threshold` are an AND, not an OR — a 300-SLOC
    but linear helper is not "god"; a 50-SLOC but 20-branch dispatcher isn't
    either. Both together are what we name.
    """
    sloc = _compute_sloc(func)
    if sloc < loc_threshold:
        return None

    state: dict[str, int] = {"n": 0}
    _count_branches(func.body, state)
    branches = state["n"]
    if branches < branch_threshold:
        return None

    return Tag(
        name="god-function",
        detail=(
            f"Function is long AND branchy: {sloc} SLOC, {branches} branches "
            f"(if/elif/for/while/except/case). "
            f"Default thresholds: {loc_threshold} SLOC & {branch_threshold} branches. "
            f"Source note: McCabe (1976) inspires the branch count; no "
            f"research-backed absolute god-function threshold exists."
        ),
        line=func.lineno,
        col=func.col_offset,
    )


# ---------------------------------------------------------------------------
# too-many-params
# ---------------------------------------------------------------------------
#
# Counts the parameters declared on the function signature:
#
#   posonly-args + args + *vararg (if present) + kwonly-args + **kwarg (if present)
#
# `self` / `cls` are NOT counted — they're the bound receiver, not a real
# parameter from the caller's perspective. This only matters for methods,
# which Tier 1 doesn't walk yet (alpha4), but the rule is future-proof.
#
# No notion of "required vs defaulted" in the count: a function with 8 params,
# all defaulted, still has 8 things the reader must understand. Defaults reduce
# boilerplate at call sites, not cognitive load on the signature.
#
# Honest source note:
#   - Martin, "Clean Code" (2008): "Three arguments... should be avoided where
#     possible. More than three... requires very special justification."
#   - Fowler, "Refactoring" (1999/2018): "Long Parameter List" — bad smell, no
#     hard number. Common tool defaults: pylint R0913=5, Sonar S107=7.
#   There is no research-backed absolute threshold. Default 5 is middle-of-road.


def _count_real_params(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count everything in `func.args` except a leading `self` / `cls`."""
    a = func.args
    # Positional-only + regular positional args, dropping a leading self/cls.
    positional = list(a.posonlyargs) + list(a.args)
    if positional and positional[0].arg in ("self", "cls"):
        positional = positional[1:]
    count = len(positional) + len(a.kwonlyargs)
    if a.vararg is not None:
        count += 1
    if a.kwarg is not None:
        count += 1
    return count


def detect_too_many_params(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    threshold: int = DEFAULT_TOO_MANY_PARAMS,
) -> Tag | None:
    """Return a `Tag` if the function signature has `threshold` or more params.

    `self` / `cls` are excluded. `*args` and `**kwargs` each count as one.
    Defaulted params count the same as required ones.
    """
    n = _count_real_params(func)
    if n < threshold:
        return None
    return Tag(
        name="too-many-params",
        detail=(
            f"Function signature has {n} parameters "
            f"(excluding self/cls; *args and **kwargs count as 1 each). "
            f"Default threshold: {threshold}. "
            f"Source note: Martin (Clean Code, 2008) recommends ≤3; pylint "
            f"R0913 defaults to 5; Sonar S107 to 7. No research-backed "
            f"absolute threshold exists."
        ),
        line=func.lineno,
        col=func.col_offset,
    )


# ---------------------------------------------------------------------------
# if-on-parameter
# ---------------------------------------------------------------------------
#
# Detects the classic "flag argument controls behavior" smell: a function that
# dispatches on one parameter's value via a chain of if/elif comparisons to
# literals. Named after Sandi Metz's "The Wrong Abstraction" (2016), where
# this pattern appears as the most concrete, narrow, checkable form.
#
# Detection algorithm:
#   1. Walk all If nodes in the function body (same-scope, no inner defs).
#   2. For each If, collect a "pivot" — a single Name node appearing as the
#      left side of a Compare to a literal constant (int / str / bytes / bool /
#      None). The elif chain is the interesting case: one If.orelse → [If].
#   3. Group by pivot name. If any single parameter name appears as the pivot
#      in `threshold` or more distinct branches, tag it.
#
# "Distinct branch" = one If node whose test directly compares the pivot.
# Nested ifs checking the same name inside a branch are NOT counted as
# separate branches — that would be a different shape of smell.
#
# Known limitation: only catches `param == literal` and `literal == param`
# directly in the test. Indirect forms (isinstance checks, lookup tables,
# dict dispatchers) are out of scope for v0.1.


def _is_compare_to_literal(
    test: ast.expr,
) -> str | None:
    """Return the pivot name if `test` is `name == literal` or `literal == name`.

    Returns None otherwise.
    """
    if not isinstance(test, ast.Compare):
        return None
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return None
    if len(test.comparators) != 1:
        return None

    left, right = test.left, test.comparators[0]
    literal_types = (ast.Constant,)

    if isinstance(left, ast.Name) and isinstance(right, literal_types):
        return left.id
    if isinstance(right, ast.Name) and isinstance(left, literal_types):
        return right.id
    return None


def _collect_if_pivots(
    stmts: list[ast.stmt],
    pivots: dict[str, int],
) -> None:
    """Walk `stmts` (same scope) and count direct-compare branches per pivot.

    For If nodes we only follow the orelse chain (elif), NOT the body.
    This keeps the detector focused on dispatch at one syntactic level —
    nested ifs inside a branch body are a separate shape of smell.

    For all other statements we recurse into their sub-bodies, so an
    if-chain inside a for-loop or try-block is still caught.
    """
    for s in stmts:
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue  # scope boundary
        if isinstance(s, ast.If):
            pivot = _is_compare_to_literal(s.test)
            if pivot is not None:
                pivots[pivot] = pivots.get(pivot, 0) + 1
            # Follow elif chains (If node directly inside orelse) but NOT s.body.
            _collect_if_pivots(s.orelse, pivots)
        else:
            for attr in ("body", "orelse", "finalbody"):
                sub = getattr(s, attr, None)
                if sub:
                    _collect_if_pivots(sub, pivots)
            if isinstance(s, ast.Try):
                for handler in s.handlers:
                    _collect_if_pivots(handler.body, pivots)
            if isinstance(s, ast.Match):
                for case in s.cases:
                    _collect_if_pivots(case.body, pivots)


def detect_if_on_parameter(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    threshold: int = DEFAULT_IF_ON_PARAMETER_BRANCHES,
) -> Tag | None:
    """Return a Tag if any parameter is used as a dispatch pivot `threshold` or more times.

    Only catches `param == literal` / `literal == param` comparisons at the
    immediate If-test level. Other dispatch forms (isinstance, dict) are out of
    scope for v0.1 (see AST_TAGS_DRAFT.md).
    """
    pivots: dict[str, int] = {}
    _collect_if_pivots(func.body, pivots)

    for name, count in pivots.items():
        if count >= threshold:
            return Tag(
                name="if-on-parameter",
                detail=(
                    f"Parameter `{name}` is compared to literals in "
                    f"{count} distinct if/elif branches (threshold: {threshold}). "
                    f"Source note: Sandi Metz, 'The Wrong Abstraction' (2016) — "
                    f"flag argument that controls behavior is the canonical example. "
                    f"v0.1 narrow form: only `param == literal` comparisons."
                ),
                line=func.lineno,
                col=func.col_offset,
            )
    return None


# ---------------------------------------------------------------------------
# magic-numbers
# ---------------------------------------------------------------------------
#
# Counts numeric literals in a function body that are NOT assigned to a named
# constant. Excludes 0, 1, -1 — universally accepted as non-magic (identity,
# boundary, sentinel).
#
# What counts as a numeric literal here:
#   - int, float, complex ast.Constant nodes with non-excluded values
#   - Does NOT count boolean True/False (they're ast.Constant but kind "bool")
#   - Does NOT count numeric literals used as default argument values in
#     nested defs (different scope, not reached)
#
# Known limitation: -0 and -1.0 are represented as UnaryOp(USub, Constant(0))
# in the AST, not as Constant(-0). The detector treats the inner Constant,
# so `-5` is correctly caught, `-1` is excluded, `-0` is excluded (maps to 0
# after negation). Complex arithmetic is not fully tracked.
#
# No research-backed threshold. Default 5 is conservative — a function with
# five or more unnamed numeric literals is almost always hiding intent.


_EXCLUDED_NUMBERS: frozenset[int | float] = frozenset({0, 1, -1})


def _is_numeric_magic(node: ast.Constant) -> bool:
    """Return True if `node` is a non-excluded numeric literal."""
    v = node.value
    if isinstance(v, bool):
        return False
    if not isinstance(v, (int, float, complex)):
        return False
    if isinstance(v, (int, float)) and v in _EXCLUDED_NUMBERS:
        return False
    return True


def _collect_magic_numbers(stmts: list[ast.stmt], out: list[ast.Constant]) -> None:
    """Walk `stmts` (same scope) and collect numeric magic literal nodes."""
    for s in stmts:
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue  # scope boundary
        for node in ast.walk(s):
            if isinstance(node, ast.Constant) and _is_numeric_magic(node):
                out.append(node)


def detect_magic_numbers(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    threshold: int = DEFAULT_MAGIC_NUMBERS_THRESHOLD,
) -> Tag | None:
    """Return a Tag if the function body contains `threshold` or more magic numbers.

    Excludes 0, 1, -1. Boolean True/False are not counted. Nested defs are
    not descended into.
    """
    found: list[ast.Constant] = []
    _collect_magic_numbers(func.body, found)

    if len(found) < threshold:
        return None

    first = found[0]
    return Tag(
        name="magic-numbers",
        detail=(
            f"Function body contains {len(found)} unexplained numeric literals "
            f"(0, 1, -1 excluded). "
            f"Default threshold: {threshold}. "
            f"Source note: no research-backed threshold — heuristic consensus "
            f"across style guides. Named constants communicate intent; literals hide it."
        ),
        line=first.lineno,
        col=first.col_offset,
    )


# ---------------------------------------------------------------------------
# dynamic-magic
# ---------------------------------------------------------------------------
#
# Binary tag — any use of Python's runtime reflection / dynamic execution builtins
# in a function body triggers it.
#
# Covered builtins (from AST_TAGS_DRAFT.md):
#   getattr, setattr, delattr, eval, exec, __import__
#
# Detection: we look for Call nodes whose func is a bare Name (e.g. `eval(...)`)
# matching the target set. Attribute-qualified calls (e.g. `builtins.eval`) are
# NOT caught in v0.1 — catching them requires resolving names across scopes, which
# is Tier 2. This is honestly documented as a known limitation.
#
# "Any occurrence" means threshold = 1, but we collect all occurrences so the
# detail message can report the count and first location.
#
# Rationale: Python docs + community consensus warn about these. No formal
# research threshold — presence alone is signal enough for a flag.


_DYNAMIC_MAGIC_NAMES: frozenset[str] = frozenset(
    {"getattr", "setattr", "delattr", "eval", "exec", "__import__"}
)


def _collect_dynamic_calls(
    stmts: list[ast.stmt], out: list[tuple[str, int, int]]
) -> None:
    """Walk `stmts` (same scope) and record (name, line, col) of dynamic calls."""
    for s in stmts:
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue  # scope boundary
        for node in ast.walk(s):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in _DYNAMIC_MAGIC_NAMES
            ):
                out.append((node.func.id, node.lineno, node.col_offset))


def detect_dynamic_magic(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Tag | None:
    """Return a Tag if the function calls any of the dynamic-magic builtins.

    Covered: getattr, setattr, delattr, eval, exec, __import__.
    Attribute-qualified calls (builtins.eval) are NOT caught in v0.1 — that
    requires cross-scope resolution (Tier 2).
    """
    found: list[tuple[str, int, int]] = []
    _collect_dynamic_calls(func.body, found)

    if not found:
        return None

    names_used = sorted({name for name, _, _ in found})
    first_name, first_line, first_col = found[0]
    return Tag(
        name="dynamic-magic",
        detail=(
            f"Function uses {len(found)} dynamic-reflection call(s): "
            f"{', '.join(names_used)}. "
            f"Source note: Python docs recommend caution with these builtins; "
            f"consensus warning, not formal research. "
            f"v0.1 gap: attribute-qualified calls (builtins.eval) not caught."
        ),
        line=first_line,
        col=first_col,
    )


# ---------------------------------------------------------------------------
# broad-except
# ---------------------------------------------------------------------------
#
# Detects bare `except:` or `except Exception:` / `except BaseException:`
# handlers anywhere inside the function body. Binary tag — any occurrence
# triggers it (we report the count and the names actually used).
#
# Nested handlers inside nested try blocks ARE caught (still the same scope).
# Inner def / class bodies are NOT descended — they are separate scopes and
# are probed independently.
#
# Only catches bare Name exception types (e.g. `except Exception:`). Attribute-
# qualified types like `except module.Exception:` require resolving names
# across imports — that is Tier 2 territory and is out of scope for v0.1.


_BROAD_EXCEPT_TYPES: frozenset[str] = frozenset({"Exception", "BaseException"})


def _collect_broad_handlers(
    stmts: list[ast.stmt], out: list[tuple[str, int, int]]
) -> None:
    for s in stmts:
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        if isinstance(s, ast.Try):
            for handler in s.handlers:
                if handler.type is None:
                    out.append(("bare except", handler.lineno, handler.col_offset))
                elif (
                    isinstance(handler.type, ast.Name)
                    and handler.type.id in _BROAD_EXCEPT_TYPES
                ):
                    out.append((handler.type.id, handler.lineno, handler.col_offset))
                _collect_broad_handlers(handler.body, out)
            _collect_broad_handlers(s.body, out)
            _collect_broad_handlers(s.orelse, out)
            _collect_broad_handlers(s.finalbody, out)
        else:
            for attr in ("body", "orelse", "finalbody"):
                sub = getattr(s, attr, None)
                if sub:
                    _collect_broad_handlers(sub, out)
            if isinstance(s, ast.Match):
                for case in s.cases:
                    _collect_broad_handlers(case.body, out)


def detect_broad_except(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Tag | None:
    found: list[tuple[str, int, int]] = []
    _collect_broad_handlers(func.body, found)
    if not found:
        return None
    kind, first_line, first_col = found[0]
    names_used = sorted({k for k, _, _ in found})
    return Tag(
        name="broad-except",
        detail=(
            f"Function has {len(found)} broad exception handler(s): "
            f"{', '.join(names_used)}. "
            f"Source note: bare except and except Exception/BaseException swallow "
            f"unexpected errors silently — specific exception types almost always "
            f"produce more debuggable code. "
            f"Ref: PEP 8, pylint W0703. "
            f"v0.1 gap: attribute-qualified types (module.Exception) not caught."
        ),
        line=first_line,
        col=first_col,
    )


# ---------------------------------------------------------------------------
# mutable-default-arg
# ---------------------------------------------------------------------------
#
# Python evaluates default values once at function definition time. When the
# default is a mutable container (list, dict, set), the SAME object is reused
# across every call — a classic gotcha that produces "ghost state" bugs.
#
# Detected: list / dict / set literal defaults on positional, positional-only,
# and keyword-only parameters. Tools that flag this: pylint W0102,
# flake8-bugbear B006.
#
# Only catches literal constructors. `def f(x=MyClass())` (a Call) is OUT of
# scope for v0.1 — semantically also a shared instance, but indistinguishable
# at the AST level from the (rare, intentional) "frozen factory" pattern. Tier
# 2 may revisit with a stricter rule.


def detect_mutable_default_arg(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Tag | None:
    found: list[tuple[str, str, int, int]] = []  # (arg_name, kind, line, col)

    positional_args = list(func.args.posonlyargs) + list(func.args.args)
    n_defaults = len(func.args.defaults)
    args_with_defaults = positional_args[len(positional_args) - n_defaults:]

    for arg, default in zip(args_with_defaults, func.args.defaults):
        if isinstance(default, ast.List):
            found.append((arg.arg, "list", default.lineno, default.col_offset))
        elif isinstance(default, ast.Dict):
            found.append((arg.arg, "dict", default.lineno, default.col_offset))
        elif isinstance(default, ast.Set):
            found.append((arg.arg, "set", default.lineno, default.col_offset))

    for arg, default in zip(func.args.kwonlyargs, func.args.kw_defaults):
        if default is None:
            continue
        if isinstance(default, ast.List):
            found.append((arg.arg, "list", default.lineno, default.col_offset))
        elif isinstance(default, ast.Dict):
            found.append((arg.arg, "dict", default.lineno, default.col_offset))
        elif isinstance(default, ast.Set):
            found.append((arg.arg, "set", default.lineno, default.col_offset))

    if not found:
        return None

    first_arg, first_kind, first_line, first_col = found[0]
    return Tag(
        name="mutable-default-arg",
        detail=(
            f"Parameter '{first_arg}' uses a mutable {first_kind} literal as default. "
            f"Python evaluates default values once at function definition — the same "
            f"object is reused across all calls. "
            f"Source note: classic Python gotcha. Use None as sentinel and create "
            f"the mutable inside the function body. "
            f"Ref: PEP 8, pylint W0102, flake8-bugbear B006. "
            f"v0.1 gap: MyClass() call defaults not caught — literals only."
        ),
        line=first_line,
        col=first_col,
    )


# ---------------------------------------------------------------------------
# too-many-returns
# ---------------------------------------------------------------------------
#
# Counts `return` statements anywhere in the function body, recursing into
# branches (if/elif/else, for/while/try/match), but stopping at scope
# boundaries (nested def / async def / class — their returns belong to a
# different function and are probed separately).
#
# Multiple exit points can signal a function doing too many things or one
# that lacks a single-exit strategy. Martin's "Clean Code" prefers single
# exit; pylint R0911 defaults to 6. We default to 4 — more conservative,
# honestly not research-backed (no v0.1 detector is, see AST_TAGS_DRAFT.md).


def _count_return_stmts(stmts: list[ast.stmt], state: dict[str, int]) -> None:
    for s in stmts:
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue  # scope boundary
        if isinstance(s, ast.Return):
            state["count"] += 1
            if state["first_line"] == 0:
                state["first_line"] = s.lineno
                state["first_col"] = s.col_offset
        for attr in ("body", "orelse", "finalbody"):
            sub = getattr(s, attr, None)
            if sub:
                _count_return_stmts(sub, state)
        if isinstance(s, ast.Try):
            for handler in s.handlers:
                _count_return_stmts(handler.body, state)
        if isinstance(s, ast.Match):
            for case in s.cases:
                _count_return_stmts(case.body, state)


def detect_too_many_returns(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    threshold: int = DEFAULT_TOO_MANY_RETURNS,
) -> Tag | None:
    state: dict[str, int] = {"count": 0, "first_line": 0, "first_col": 0}
    _count_return_stmts(func.body, state)
    if state["count"] < threshold:
        return None
    return Tag(
        name="too-many-returns",
        detail=(
            f"Function has {state['count']} return statements (threshold: {threshold}). "
            f"Multiple exit points can signal a function handling too many cases "
            f"or lacking a single-exit strategy. "
            f"Source note: Martin, Clean Code (2008) prefers single exit; "
            f"no hard research-backed threshold. pylint R0911 defaults to 6."
        ),
        line=state["first_line"] or func.lineno,
        col=state["first_col"] or func.col_offset,
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
    ("god-function", detect_god_function),
    ("too-many-params", detect_too_many_params),
    ("if-on-parameter", detect_if_on_parameter),
    ("magic-numbers", detect_magic_numbers),
    ("dynamic-magic", detect_dynamic_magic),
    ("broad-except", detect_broad_except),
    ("mutable-default-arg", detect_mutable_default_arg),
    ("too-many-returns", detect_too_many_returns),
)


# ---------------------------------------------------------------------------
# god-class
# ---------------------------------------------------------------------------
#
# Two coupled signals on a class: number of methods declared directly in the
# body, and number of distinct instance attributes assigned via `self.X = ...`
# inside __init__.
#
# Flag rules:
#   methods > 15                                       → god-class
#   methods > 8 AND instance_attributes > 5            → god-class
#
# Method count: direct FunctionDef + AsyncFunctionDef inside ClassDef.body.
# @staticmethod / @classmethod methods count the same — they are still
# FunctionDef nodes; the decorators don't change the AST type. Methods on
# nested classes do NOT contribute to the outer class — only the nested
# class itself sees them.
#
# Attribute count: distinct names X assigned via `self.X = ...` (or augmented
# / annotated assignments) inside the class's __init__. We don't trace flow
# through helper methods called from __init__ — that's a different shape of
# work and Tier 2 territory.
#
# No research-backed thresholds. Numbers chosen as conservative defaults; the
# AND-condition prevents flagging dataclass-style classes (many fields, few
# methods) and pure-method utility classes (many methods, no state).


def _count_direct_methods(cls: ast.ClassDef) -> int:
    return sum(
        1
        for n in cls.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    )


def _find_init(cls: ast.ClassDef) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for n in cls.body:
        if (
            isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
            and n.name == "__init__"
        ):
            return n
    return None


def _collect_self_attrs(stmts: list[ast.stmt], names: set[str]) -> None:
    """Record every `self.X` target name written inside `stmts` (recursive)."""
    for s in stmts:
        if isinstance(s, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue  # scope boundary — nested defs in __init__ don't count
        for node in ast.walk(s):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    _record_self_target(target, names)
            elif isinstance(node, ast.AugAssign | ast.AnnAssign):
                _record_self_target(node.target, names)


def _record_self_target(target: ast.expr, names: set[str]) -> None:
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    ):
        names.add(target.attr)
    elif isinstance(target, ast.Tuple | ast.List):
        for elt in target.elts:
            _record_self_target(elt, names)


def detect_god_class(
    cls: ast.ClassDef,
    classes_in_file: "dict[str, ast.ClassDef] | None" = None,
) -> list[dict]:
    """Return a list of god-class flag dicts (0 or 1 element).

    Returned dict shape: {tag, lineno, col_offset, detail}.
    The list shape is uniform with other class-level detectors and leaves
    room for future multi-flag detectors without changing the call site.
    """
    methods = _count_direct_methods(cls)
    init = _find_init(cls)
    attrs: set[str] = set()
    if init is not None:
        _collect_self_attrs(init.body, attrs)
    n_attrs = len(attrs)

    if methods > 15 or (methods > 8 and n_attrs > 5):
        return [
            {
                "tag": "god-class",
                "lineno": cls.lineno,
                "col_offset": cls.col_offset,
                "detail": f"{methods} methods, {n_attrs} attrs",
            }
        ]
    return []


# ---------------------------------------------------------------------------
# deep-inheritance
# ---------------------------------------------------------------------------
#
# Two signals on a class:
#   - multiple inheritance: more than one base, where at least one base is
#     not the literal `object`. Pure single inheritance and `class C(object):`
#     do not flag.
#   - depth: longest chain of bases resolvable to ClassDef nodes in the SAME
#     file. Capped at 4 levels of walking to avoid pathological recursion;
#     unresolved bases (imports, builtins) terminate the chain at +1.
#
# Flag rules:
#   len(bases) > 1 AND not all bases are `object`     → deep-inheritance
#   depth > 3                                          → deep-inheritance
#
# Depth convention: a class with no bases has depth 1. `class B(A)` where A
# is in this file and has no bases has depth 2. The chain A←B←C←D yields
# depth 4 and flags D.


_OBJECT_NAME = "object"


def _is_object_base(base: ast.expr) -> bool:
    return isinstance(base, ast.Name) and base.id == _OBJECT_NAME


def _non_trivial_bases(cls: ast.ClassDef) -> list[ast.expr]:
    return [b for b in cls.bases if not _is_object_base(b)]


def _inheritance_depth(
    cls: ast.ClassDef,
    classes_in_file: dict[str, ast.ClassDef],
    max_walk: int = 4,
    seen: frozenset[str] = frozenset(),
) -> int:
    """Length of longest base chain reachable from `cls` within this file.

    Returns 1 for a class with no bases. Each resolved parent adds one. An
    unresolved base (foreign name, attribute access, etc.) adds 1 and then
    stops. `max_walk` caps recursion depth; cycles are blocked via `seen`.
    """
    if not cls.bases:
        return 1
    if max_walk <= 0:
        return 1
    if cls.name in seen:
        return 1
    next_seen = seen | {cls.name}

    best = 1
    for base in cls.bases:
        if isinstance(base, ast.Name):
            parent = classes_in_file.get(base.id)
            if parent is not None:
                candidate = (
                    _inheritance_depth(parent, classes_in_file, max_walk - 1, next_seen)
                    + 1
                )
            else:
                candidate = 2  # foreign / builtin parent — chain stops here
        else:
            candidate = 2  # attribute / call / subscript base — opaque
        if candidate > best:
            best = candidate
    return best


def detect_deep_inheritance(
    cls: ast.ClassDef,
    classes_in_file: dict[str, ast.ClassDef] | None = None,
) -> list[dict]:
    """Return a list of deep-inheritance flag dicts (0 or 1 element).

    `classes_in_file` lets the depth check resolve same-file parents. When
    omitted, the detector still catches multiple inheritance.
    """
    classes_in_file = classes_in_file or {}

    multi = len(cls.bases) > 1 and len(_non_trivial_bases(cls)) >= 1
    depth = _inheritance_depth(cls, classes_in_file)

    if multi or depth > 3:
        reasons: list[str] = []
        if multi:
            reasons.append(f"multi-inheritance ({len(cls.bases)} bases)")
        if depth > 3:
            reasons.append(f"depth {depth}")
        return [
            {
                "tag": "deep-inheritance",
                "lineno": cls.lineno,
                "col_offset": cls.col_offset,
                "detail": ", ".join(reasons),
            }
        ]
    return []


# ---------------------------------------------------------------------------
# Registry of Tier 1 class-level detectors
# ---------------------------------------------------------------------------
#
# Parallel to TIER1_DETECTORS, but for ClassDef-level signals. Each callable
# takes an ast.ClassDef and (optionally) a {name: ClassDef} map for same-file
# resolution, and returns a list of flag dicts {tag, lineno, col_offset,
# detail}. Empty list = no flag.

TIER1_CLASS_DETECTORS: tuple[
    tuple[str, "object"], ...
] = (
    ("god-class", detect_god_class),
    ("deep-inheritance", detect_deep_inheritance),
)
