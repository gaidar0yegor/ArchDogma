"""Tests for the catalog validator — six ADR-002 rules.

Each rule has a positive test (real catalog is clean against it) and at
least one negative test (a synthetic catalog that trips it). Rules are
numbered per ADR-002.
"""

from __future__ import annotations

from archdogma.catalog.loader import Catalog, CandidateRef, DogmaRef, load_catalog
from archdogma.catalog.validator import (
    ValidationIssue,
    has_errors,
    validate_catalog,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dogma(
    id_: str,
    number: int,
    *,
    status: str = "filled",
    v01_priority: bool = False,
    raw_overrides: dict | None = None,
) -> DogmaRef:
    raw = {
        "id": id_,
        "number": number,
        "title": id_.upper(),
        "status": status,
        "v01_priority": v01_priority,
    }
    if raw_overrides:
        raw.update(raw_overrides)
    return DogmaRef(
        id=id_,
        number=number,
        title=id_.upper(),
        status=status,
        v01_priority=v01_priority,
        raw=raw,
    )


def _cat(
    dogmas: tuple[DogmaRef, ...] = (),
    candidates: tuple[CandidateRef, ...] = (),
) -> Catalog:
    return Catalog(
        schema_version=1,
        dogmas=dogmas,
        candidates=candidates,
        tag_index={},
    )


def _rules_in(issues: list[ValidationIssue]) -> set[int]:
    return {i.rule for i in issues}


# ---------------------------------------------------------------------------
# Real catalog is clean — regression guard for everything
# ---------------------------------------------------------------------------


def test_real_catalog_is_clean() -> None:
    issues = validate_catalog(load_catalog())
    assert issues == [], f"real catalog has issues: {issues}"


# ---------------------------------------------------------------------------
# Rule 1 — counter_dogmas[].attribution required
# ---------------------------------------------------------------------------


def test_rule1_missing_attribution_is_error() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "counter_dogmas": [
                {"name": "NoAuthor", "thesis": "Nope."},
            ]
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert 1 in _rules_in(issues)
    assert has_errors(issues)


def test_rule1_empty_attribution_string_is_error() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "counter_dogmas": [
                {"name": "Empty", "attribution": "   ", "thesis": "Nope."},
            ]
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert any(i.rule == 1 for i in issues)


def test_rule1_valid_attribution_passes() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "counter_dogmas": [
                {"name": "X", "attribution": "Author 2024", "thesis": "."},
            ]
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert not any(i.rule == 1 for i in issues)


# ---------------------------------------------------------------------------
# Rule 2 — case references have known shape
# ---------------------------------------------------------------------------


def test_rule2_marker_string_is_valid() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={"failure_cases": "need_postmortems"},
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert not any(i.rule == 2 for i in issues)


def test_rule2_unknown_marker_is_error() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={"failure_cases": "need_whatever"},
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert any(i.rule == 2 and i.severity == "error" for i in issues)


def test_rule2_list_of_mappings_is_valid() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "success_cases": [
                {"title": "Case A", "source_url": "https://example.com"},
            ]
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert not any(i.rule == 2 for i in issues)


def test_rule2_list_item_missing_title_is_warning() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "success_cases": [{"source_url": "https://example.com"}]
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    rule2 = [i for i in issues if i.rule == 2]
    assert rule2 and all(i.severity == "warning" for i in rule2)


def test_rule2_non_string_non_list_is_error() -> None:
    d = _dogma("x", 1, raw_overrides={"failure_cases": 42})
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert any(i.rule == 2 and i.severity == "error" for i in issues)


# ---------------------------------------------------------------------------
# Rule 3 — ids unique across dogmas + candidates
# ---------------------------------------------------------------------------


def test_rule3_duplicate_dogma_ids_error() -> None:
    issues = validate_catalog(
        _cat(dogmas=(_dogma("x", 1), _dogma("x", 2)))
    )
    assert any(i.rule == 3 for i in issues)


def test_rule3_dogma_and_candidate_same_id_error() -> None:
    c = CandidateRef(id="x", title="Candidate X", raw={"id": "x", "title": "C"})
    issues = validate_catalog(
        _cat(dogmas=(_dogma("x", 1),), candidates=(c,))
    )
    assert any(i.rule == 3 for i in issues)


# ---------------------------------------------------------------------------
# Rule 4 — numbers unique AND sequential from 1
# ---------------------------------------------------------------------------


def test_rule4_duplicate_numbers_error() -> None:
    issues = validate_catalog(
        _cat(dogmas=(_dogma("a", 1), _dogma("b", 1)))
    )
    assert any(i.rule == 4 for i in issues)


def test_rule4_gap_in_sequence_error() -> None:
    # 1, 2, 4 — missing 3.
    issues = validate_catalog(
        _cat(dogmas=(_dogma("a", 1), _dogma("b", 2), _dogma("c", 4)))
    )
    assert any(i.rule == 4 for i in issues)


def test_rule4_starting_at_two_is_error() -> None:
    issues = validate_catalog(_cat(dogmas=(_dogma("a", 2), _dogma("b", 3))))
    assert any(i.rule == 4 for i in issues)


def test_rule4_sequential_from_one_passes() -> None:
    issues = validate_catalog(
        _cat(dogmas=(_dogma("a", 1), _dogma("b", 2), _dogma("c", 3)))
    )
    assert not any(i.rule == 4 for i in issues)


# ---------------------------------------------------------------------------
# Rule 5 — v01_priority ⇒ status != stub
# ---------------------------------------------------------------------------


def test_rule5_priority_stub_is_error() -> None:
    issues = validate_catalog(
        _cat(dogmas=(_dogma("x", 1, status="stub", v01_priority=True),))
    )
    assert any(i.rule == 5 for i in issues)


def test_rule5_priority_draft_passes() -> None:
    issues = validate_catalog(
        _cat(dogmas=(_dogma("x", 1, status="draft", v01_priority=True),))
    )
    assert not any(i.rule == 5 for i in issues)


def test_rule5_stub_without_priority_passes() -> None:
    issues = validate_catalog(
        _cat(dogmas=(_dogma("x", 1, status="stub", v01_priority=False),))
    )
    assert not any(i.rule == 5 for i in issues)


# ---------------------------------------------------------------------------
# Rule 6 — honest_verdict.status: final requires full narrative
# ---------------------------------------------------------------------------


def test_rule6_final_without_follow_when_is_error() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "honest_verdict": {
                "status": "final",
                # follow_when missing
                "break_when": ["x"],
                "main_signal": "y",
            }
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert any(i.rule == 6 for i in issues)


def test_rule6_final_with_empty_main_signal_is_error() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "honest_verdict": {
                "status": "final",
                "follow_when": ["a"],
                "break_when": ["b"],
                "main_signal": "   ",
            }
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert any(i.rule == 6 for i in issues)


def test_rule6_draft_verdict_can_have_empty_fields() -> None:
    """Only `status: final` is strict. `draft_awaiting_cases` is deliberately
    loose — we're honest about not having the cases yet."""
    d = _dogma(
        "x",
        1,
        raw_overrides={"honest_verdict": {"status": "draft_awaiting_cases"}},
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert not any(i.rule == 6 for i in issues)


def test_rule6_final_with_all_fields_passes() -> None:
    d = _dogma(
        "x",
        1,
        raw_overrides={
            "honest_verdict": {
                "status": "final",
                "follow_when": ["a"],
                "break_when": ["b"],
                "main_signal": "c",
            }
        },
    )
    issues = validate_catalog(_cat(dogmas=(d,)))
    assert not any(i.rule == 6 for i in issues)


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_issues_are_sorted_deterministically() -> None:
    # Two breaks of rules 3 and 5; validator must return them in stable order.
    d1 = _dogma("dup", 1, status="stub", v01_priority=True)
    d2 = _dogma("dup", 2)
    issues = validate_catalog(_cat(dogmas=(d1, d2)))
    # Sorted by (rule, entity, message).
    assert issues == sorted(
        issues, key=lambda i: (i.rule, i.entity, i.message)
    )


def test_has_errors_true_when_any_error_present() -> None:
    issues = [
        ValidationIssue(rule=1, severity="warning", entity="x", message="m"),
        ValidationIssue(rule=2, severity="error", entity="y", message="m2"),
    ]
    assert has_errors(issues)


def test_has_errors_false_on_warnings_only() -> None:
    issues = [
        ValidationIssue(rule=1, severity="warning", entity="x", message="m"),
    ]
    assert not has_errors(issues)
