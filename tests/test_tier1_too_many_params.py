"""Unit tests for the too-many-params detector.

Signal = len(positional args) + len(kwonly args) + (1 if *args) + (1 if **kwargs),
with a leading `self` / `cls` dropped.

`self`/`cls` exclusion is future-proof for alpha4 (class-method probe). At this
tier we still only see top-level `def`, so it's a policy placeholder, not a
working-today feature — but the rule is the rule.
"""

from __future__ import annotations

import ast

import pytest

from archdogma.probe.tags.tier1 import (
    DEFAULT_TOO_MANY_PARAMS,
    TIER1_DETECTORS,
    Tag,
    _count_real_params,
    detect_too_many_params,
)


def _first_func(source: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


def _method_of(source: str, method_name: str = "m") -> ast.FunctionDef:
    """Pull a method out of a class body so we can hit self/cls exclusion."""
    tree = ast.parse(source)
    cls = tree.body[0]
    assert isinstance(cls, ast.ClassDef)
    for node in cls.body:
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == method_name
        ):
            assert isinstance(node, ast.FunctionDef)
            return node
    raise AssertionError(f"method {method_name} not found")


# ---------------------------------------------------------------------------
# Default threshold pins what AST_TAGS_DRAFT.md / registry expect
# ---------------------------------------------------------------------------


def test_default_threshold_is_five() -> None:
    assert DEFAULT_TOO_MANY_PARAMS == 5


def test_registered_in_tier1_registry() -> None:
    names = [name for name, _ in TIER1_DETECTORS]
    assert "too-many-params" in names


# ---------------------------------------------------------------------------
# Threshold boundary cases
# ---------------------------------------------------------------------------


def test_zero_params_no_tag() -> None:
    func = _first_func("def f():\n    pass\n")
    assert detect_too_many_params(func) is None


def test_below_threshold_no_tag() -> None:
    func = _first_func("def f(a, b, c, d):\n    pass\n")  # 4 params
    assert detect_too_many_params(func) is None


def test_at_threshold_triggers() -> None:
    func = _first_func("def f(a, b, c, d, e):\n    pass\n")  # 5 params
    tag = detect_too_many_params(func)
    assert isinstance(tag, Tag)
    assert tag.name == "too-many-params"
    assert "5 parameters" in tag.detail


def test_above_threshold_triggers() -> None:
    func = _first_func("def f(a, b, c, d, e, f, g):\n    pass\n")  # 7
    tag = detect_too_many_params(func)
    assert tag is not None
    assert "7 parameters" in tag.detail


def test_custom_threshold_respected() -> None:
    func = _first_func("def f(a, b, c):\n    pass\n")  # 3
    assert detect_too_many_params(func, threshold=3) is not None
    assert detect_too_many_params(func, threshold=4) is None


# ---------------------------------------------------------------------------
# Parameter shape — what counts as one parameter
# ---------------------------------------------------------------------------


def test_positional_only_args_counted() -> None:
    func = _first_func("def f(a, b, /, c, d):\n    pass\n")
    assert _count_real_params(func) == 4


def test_keyword_only_args_counted() -> None:
    func = _first_func("def f(a, b, *, c, d, e):\n    pass\n")
    # a, b + c, d, e (vararg is the `*` separator, no name) → 5
    assert _count_real_params(func) == 5


def test_vararg_counts_as_one() -> None:
    func = _first_func("def f(a, *args):\n    pass\n")
    # a + *args → 2 (not "however-many things the caller passes")
    assert _count_real_params(func) == 2


def test_kwarg_counts_as_one() -> None:
    func = _first_func("def f(a, **kwargs):\n    pass\n")
    # a + **kwargs → 2
    assert _count_real_params(func) == 2


def test_vararg_and_kwarg_counted_together() -> None:
    func = _first_func("def f(a, b, *args, **kwargs):\n    pass\n")
    # a, b + *args + **kwargs → 4
    assert _count_real_params(func) == 4


def test_default_values_dont_discount() -> None:
    """Defaults reduce call-site noise, not signature complexity.
    Eight things with defaults are still eight things."""
    func = _first_func(
        "def f(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8):\n    pass\n"
    )
    assert _count_real_params(func) == 8
    assert detect_too_many_params(func) is not None


def test_bare_star_separator_not_counted() -> None:
    """`def f(a, b, *, c)` — the `*` is a marker, not a param."""
    func = _first_func("def f(a, b, *, c):\n    pass\n")
    # a, b, c → 3
    assert _count_real_params(func) == 3


# ---------------------------------------------------------------------------
# self / cls exclusion (forward-looking; future-proof for alpha4 class probe)
# ---------------------------------------------------------------------------


def test_self_not_counted_in_method() -> None:
    func = _method_of(
        "class C:\n    def m(self, a, b, c, d, e):\n        pass\n"
    )
    # self excluded → 5 real params
    assert _count_real_params(func) == 5
    assert detect_too_many_params(func) is not None


def test_cls_not_counted_in_classmethod() -> None:
    func = _method_of(
        "class C:\n    @classmethod\n    def m(cls, a, b, c, d):\n        pass\n"
    )
    # cls excluded → 4 real params, below threshold
    assert _count_real_params(func) == 4
    assert detect_too_many_params(func) is None


def test_self_as_second_arg_is_counted() -> None:
    """Only a *leading* self/cls is dropped. If the reader named the second
    arg `self`, that's a real parameter."""
    func = _first_func("def f(x, self):\n    pass\n")
    assert _count_real_params(func) == 2


def test_self_like_name_in_positional_only_counts() -> None:
    """Posonly-ordering is respected: a leading `self` in posonlyargs still
    gets dropped (it's the bound receiver in posonly form)."""
    func = _first_func("def f(self, a, /, b):\n    pass\n")
    # self dropped → a + b
    assert _count_real_params(func) == 2


# ---------------------------------------------------------------------------
# async def is handled same as def
# ---------------------------------------------------------------------------


def test_async_def_counted_same() -> None:
    tree = ast.parse(
        "async def f(a, b, c, d, e, f_):\n    pass\n"
    )
    node = tree.body[0]
    assert isinstance(node, ast.AsyncFunctionDef)
    tag = detect_too_many_params(node)
    assert tag is not None
    assert "6 parameters" in tag.detail


# ---------------------------------------------------------------------------
# Tag shape — location + honest source note
# ---------------------------------------------------------------------------


def test_tag_points_at_function_signature() -> None:
    func = _first_func("def f(a, b, c, d, e, f):\n    pass\n")
    tag = detect_too_many_params(func)
    assert tag is not None
    assert tag.line == func.lineno
    assert tag.col == func.col_offset


def test_tag_detail_mentions_honest_sources() -> None:
    func = _first_func("def f(a, b, c, d, e):\n    pass\n")
    tag = detect_too_many_params(func)
    assert tag is not None
    # Source note honestly names both ends of the range.
    assert "Martin" in tag.detail
    assert "pylint" in tag.detail
    assert "Sonar" in tag.detail
    assert "No research-backed" in tag.detail


def test_tag_detail_explains_self_and_varargs_rule() -> None:
    func = _first_func("def f(a, b, c, d, e):\n    pass\n")
    tag = detect_too_many_params(func)
    assert tag is not None
    assert "self/cls" in tag.detail
    assert "*args" in tag.detail and "**kwargs" in tag.detail


# ---------------------------------------------------------------------------
# Extreme shapes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n", [5, 10, 20, 50])
def test_scales_with_many_params(n: int) -> None:
    params = ", ".join(f"a{i}" for i in range(n))
    func = _first_func(f"def f({params}):\n    pass\n")
    assert _count_real_params(func) == n
    tag = detect_too_many_params(func)
    assert tag is not None
    assert f"{n} parameters" in tag.detail
