"""Unit tests for the god-class detector.

Two coupled signals: number of methods declared directly in the class body,
and number of distinct instance attributes assigned via `self.X = ...` in
__init__. Flag if methods > 15 OR (methods > 8 AND attrs > 5).

Method count includes @staticmethod / @classmethod (still FunctionDef nodes).
Methods on nested classes belong to the nested class, not the outer one.
"""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    TIER1_CLASS_DETECTORS,
    detect_god_class,
)


def _first_class(source: str) -> ast.ClassDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.ClassDef)
    return node


def _all_classes(source: str) -> list[ast.ClassDef]:
    tree = ast.parse(source)
    return [n for n in tree.body if isinstance(n, ast.ClassDef)]


def _methods(names: list[str]) -> str:
    """Build a class body of trivial methods with the given names."""
    return "\n".join(f"    def {n}(self): pass" for n in names)


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------


def test_registered_in_class_registry() -> None:
    names = [name for name, _ in TIER1_CLASS_DETECTORS]
    assert "god-class" in names


# ---------------------------------------------------------------------------
# Below-threshold: clean classes
# ---------------------------------------------------------------------------


def test_clean_class_few_methods_no_flag() -> None:
    src = "class C:\n" + _methods(["a", "b", "c"]) + "\n"
    assert detect_god_class(_first_class(src)) == []


def test_empty_class_no_flag() -> None:
    src = "class C:\n    pass\n"
    assert detect_god_class(_first_class(src)) == []


def test_eight_methods_four_attrs_no_flag() -> None:
    """Under both branches: 8 methods (need >8) and 4 attrs (need >5)."""
    src = (
        "class C:\n"
        "    def __init__(self):\n"
        "        self.a = 1\n"
        "        self.b = 2\n"
        "        self.c = 3\n"
        "        self.d = 4\n"
        + _methods(["m1", "m2", "m3", "m4", "m5", "m6", "m7"])
        + "\n"
    )
    cls = _first_class(src)
    # __init__ + 7 methods = 8 methods total. 4 attrs.
    assert detect_god_class(cls) == []


# ---------------------------------------------------------------------------
# Above-threshold: god-classes
# ---------------------------------------------------------------------------


def test_sixteen_methods_flagged() -> None:
    names = [f"m{i}" for i in range(16)]
    src = "class C:\n" + _methods(names) + "\n"
    flags = detect_god_class(_first_class(src))
    assert len(flags) == 1
    flag = flags[0]
    assert flag["tag"] == "god-class"
    assert flag["lineno"] == 1
    assert flag["col_offset"] == 0
    assert "16 methods" in flag["detail"]


def test_nine_methods_six_attrs_flagged() -> None:
    """Triggers the AND branch: methods>8 AND attrs>5."""
    src = (
        "class C:\n"
        "    def __init__(self):\n"
        "        self.a = 1\n"
        "        self.b = 2\n"
        "        self.c = 3\n"
        "        self.d = 4\n"
        "        self.e = 5\n"
        "        self.f = 6\n"
        + _methods(["m1", "m2", "m3", "m4", "m5", "m6", "m7", "m8"])
        + "\n"
    )
    cls = _first_class(src)
    # __init__ + 8 methods = 9 methods. 6 attrs.
    flags = detect_god_class(cls)
    assert len(flags) == 1
    assert flags[0]["tag"] == "god-class"
    assert "9 methods" in flags[0]["detail"]
    assert "6 attrs" in flags[0]["detail"]


# ---------------------------------------------------------------------------
# Multiple classes — only god ones flagged
# ---------------------------------------------------------------------------


def test_multiple_classes_only_god_flagged() -> None:
    big = _methods([f"m{i}" for i in range(20)])
    small = _methods(["a", "b"])
    src = f"class Big:\n{big}\n\nclass Small:\n{small}\n"
    classes = _all_classes(src)
    flags_big = detect_god_class(classes[0])
    flags_small = detect_god_class(classes[1])
    assert len(flags_big) == 1
    assert flags_small == []


# ---------------------------------------------------------------------------
# Static / classmethod still count as methods
# ---------------------------------------------------------------------------


def test_static_and_class_methods_count() -> None:
    """16 methods, mixed regular / static / class — all count."""
    body_lines = []
    for i in range(6):
        body_lines.append(f"    def m{i}(self): pass")
    for i in range(5):
        body_lines.append("    @staticmethod")
        body_lines.append(f"    def s{i}(): pass")
    for i in range(5):
        body_lines.append("    @classmethod")
        body_lines.append(f"    def c{i}(cls): pass")
    src = "class C:\n" + "\n".join(body_lines) + "\n"
    cls = _first_class(src)
    flags = detect_god_class(cls)
    assert len(flags) == 1
    assert "16 methods" in flags[0]["detail"]


# ---------------------------------------------------------------------------
# Nested classes — methods belong to the inner class only
# ---------------------------------------------------------------------------


def test_nested_class_methods_dont_count_for_outer() -> None:
    """Outer has 2 direct methods + a nested class with many methods.
    Outer must NOT be flagged because the nested class's methods are scoped
    to the nested class.
    """
    src = (
        "class Outer:\n"
        "    def a(self): pass\n"
        "    def b(self): pass\n"
        "    class Inner:\n"
        + "\n".join(f"        def m{i}(self): pass" for i in range(20))
        + "\n"
    )
    outer = _first_class(src)
    flags_outer = detect_god_class(outer)
    assert flags_outer == []

    # And the Inner class, when probed directly, IS flagged.
    inner = next(
        n for n in outer.body if isinstance(n, ast.ClassDef) and n.name == "Inner"
    )
    flags_inner = detect_god_class(inner)
    assert len(flags_inner) == 1
    assert flags_inner[0]["tag"] == "god-class"


# ---------------------------------------------------------------------------
# Attribute counting details
# ---------------------------------------------------------------------------


def test_repeated_attr_names_counted_once() -> None:
    """self.x assigned twice still counts as one distinct attribute."""
    src = (
        "class C:\n"
        "    def __init__(self):\n"
        "        self.x = 1\n"
        "        self.x = 2\n"
        + _methods([f"m{i}" for i in range(8)])
        + "\n"
    )
    cls = _first_class(src)
    # 9 methods total, 1 attr → does NOT trip the AND branch (attrs>5 fails).
    assert detect_god_class(cls) == []


def test_no_init_means_zero_attrs() -> None:
    """Class with many methods but no __init__: only the >15 branch can fire."""
    src = "class C:\n" + _methods([f"m{i}" for i in range(10)]) + "\n"
    cls = _first_class(src)
    # 10 methods, 0 attrs — 10>8 but 0 not >5, and 10 not >15. No flag.
    assert detect_god_class(cls) == []


def test_tuple_self_assignment_counts_attrs() -> None:
    """self.a, self.b = 1, 2 should record both attribute names."""
    src = (
        "class C:\n"
        "    def __init__(self):\n"
        "        self.a, self.b, self.c, self.d, self.e, self.f = 1,2,3,4,5,6\n"
        + _methods([f"m{i}" for i in range(8)])
        + "\n"
    )
    cls = _first_class(src)
    # 9 methods (init + 8), 6 attrs → flag via AND branch.
    flags = detect_god_class(cls)
    assert len(flags) == 1
    assert "6 attrs" in flags[0]["detail"]
