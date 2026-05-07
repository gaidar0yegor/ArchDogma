"""Unit tests for the deep-inheritance detector.

Two signals:
  - multiple inheritance: more than one base, with at least one non-`object`
    base. `class C(object)` does NOT flag; `class C(A, object)` does.
  - depth: longest base chain resolvable to ClassDef nodes in the same file.
    A class with no bases has depth 1; A←B←C←D yields depth 4 → flag for D.
"""

from __future__ import annotations

import ast

from archdogma.probe.tags.tier1 import (
    TIER1_CLASS_DETECTORS,
    detect_deep_inheritance,
)


def _classes_by_name(source: str) -> dict[str, ast.ClassDef]:
    tree = ast.parse(source)
    return {
        n.name: n for n in tree.body if isinstance(n, ast.ClassDef)
    }


def _first_class(source: str) -> ast.ClassDef:
    tree = ast.parse(source)
    node = tree.body[0]
    assert isinstance(node, ast.ClassDef)
    return node


# ---------------------------------------------------------------------------
# Registry contract
# ---------------------------------------------------------------------------


def test_registered_in_class_registry() -> None:
    names = [name for name, _ in TIER1_CLASS_DETECTORS]
    assert "deep-inheritance" in names


# ---------------------------------------------------------------------------
# Single base / no base — never flagged on multi-inheritance grounds
# ---------------------------------------------------------------------------


def test_no_base_no_flag() -> None:
    src = "class C:\n    pass\n"
    assert detect_deep_inheritance(_first_class(src), {}) == []


def test_single_base_no_flag() -> None:
    src = "class A:\n    pass\nclass B(A):\n    pass\n"
    by_name = _classes_by_name(src)
    assert detect_deep_inheritance(by_name["B"], by_name) == []


def test_only_object_no_flag() -> None:
    src = "class C(object):\n    pass\n"
    assert detect_deep_inheritance(_first_class(src), {}) == []


# ---------------------------------------------------------------------------
# Multiple inheritance
# ---------------------------------------------------------------------------


def test_two_non_trivial_bases_flagged() -> None:
    src = (
        "class A:\n    pass\n"
        "class B:\n    pass\n"
        "class C(A, B):\n    pass\n"
    )
    by_name = _classes_by_name(src)
    flags = detect_deep_inheritance(by_name["C"], by_name)
    assert len(flags) == 1
    assert flags[0]["tag"] == "deep-inheritance"
    assert "multi-inheritance" in flags[0]["detail"]


def test_a_and_object_flagged() -> None:
    """class C(A, object): one non-trivial base + object → still flagged
    because it's multiple inheritance and not all bases are object."""
    src = "class A:\n    pass\nclass C(A, object):\n    pass\n"
    by_name = _classes_by_name(src)
    flags = detect_deep_inheritance(by_name["C"], by_name)
    assert len(flags) == 1
    assert flags[0]["tag"] == "deep-inheritance"


def test_diamond_flagged() -> None:
    src = (
        "class A:\n    pass\n"
        "class B(A):\n    pass\n"
        "class C(A):\n    pass\n"
        "class D(B, C):\n    pass\n"
    )
    by_name = _classes_by_name(src)
    flags = detect_deep_inheritance(by_name["D"], by_name)
    assert len(flags) == 1
    assert flags[0]["tag"] == "deep-inheritance"


def test_mixin_pattern_flagged() -> None:
    src = (
        "class Base:\n    pass\n"
        "class LogMixin:\n    pass\n"
        "class C(Base, LogMixin):\n    pass\n"
    )
    by_name = _classes_by_name(src)
    flags = detect_deep_inheritance(by_name["C"], by_name)
    assert len(flags) == 1
    assert flags[0]["tag"] == "deep-inheritance"


# ---------------------------------------------------------------------------
# Depth chain
# ---------------------------------------------------------------------------


def test_depth_four_chain_flags_only_leaf() -> None:
    """A←B←C←D — depth 4 flags D. A, B, C remain unflagged on depth grounds."""
    src = (
        "class A:\n    pass\n"
        "class B(A):\n    pass\n"
        "class C(B):\n    pass\n"
        "class D(C):\n    pass\n"
    )
    by_name = _classes_by_name(src)
    assert detect_deep_inheritance(by_name["A"], by_name) == []
    assert detect_deep_inheritance(by_name["B"], by_name) == []
    assert detect_deep_inheritance(by_name["C"], by_name) == []
    flags_d = detect_deep_inheritance(by_name["D"], by_name)
    assert len(flags_d) == 1
    assert flags_d[0]["tag"] == "deep-inheritance"
    assert "depth 4" in flags_d[0]["detail"]


def test_depth_three_chain_no_flag() -> None:
    """A←B←C — depth 3 is the boundary; > 3 means >= 4. C does not flag."""
    src = (
        "class A:\n    pass\n"
        "class B(A):\n    pass\n"
        "class C(B):\n    pass\n"
    )
    by_name = _classes_by_name(src)
    assert detect_deep_inheritance(by_name["C"], by_name) == []


def test_foreign_base_does_not_extend_depth() -> None:
    """Bases that aren't ClassDef in this file count as +1 only."""
    src = "class C(SomeImported):\n    pass\n"
    cls = _first_class(src)
    # No same-file lookup → depth = 2, well below the > 3 threshold.
    assert detect_deep_inheritance(cls, {}) == []
