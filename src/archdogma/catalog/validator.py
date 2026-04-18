"""Catalog validator — six rules from ADR-002 §"Правила, которые будет проверять валидатор".

Rules (numbered per ADR-002 order):

1. `counter_dogmas[].attribution` is required. Missing → error.
2. Case references (`failure_cases`, `success_cases`) must be either a
   marker string (`need_postmortems` / `need_data`) or a structured list
   of `{title, source_url, summary}`. Stray scalars of other shapes → error.
3. `id` is unique across `dogmas` + `candidates`.
4. `number` on dogmas is unique AND sequential from 1.
5. `v01_priority: true` ⇒ `status != "stub"` (priority dogmas must be ≥ draft).
6. `honest_verdict.status: final` ⇒ non-empty `follow_when`, `break_when`,
   `main_signal`.

Output: a list of `ValidationIssue`. Severity `error` = must-fix,
`warning` = fix-soon. The CLI command exits non-zero iff at least one
error is present.

Deliberate non-goals:
- URL live-check. That's `--check-urls`, a different command, probably
  offline-by-default for CI hygiene.
- YAML well-formedness. The loader raises before we ever get here.
- Schema mismatch (e.g., misspelled top-level key). Also loader's job.
"""

from __future__ import annotations

from dataclasses import dataclass

from archdogma.catalog.loader import Catalog, DogmaRef

CASE_MARKERS = frozenset({"need_postmortems", "need_data", "need_cases"})


@dataclass(frozen=True)
class ValidationIssue:
    rule: int  # 1–6, per ADR-002 ordering
    severity: str  # "error" | "warning"
    entity: str  # e.g. "dogma:dry" | "candidate:god-class" | "catalog"
    message: str


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_catalog(catalog: Catalog) -> list[ValidationIssue]:
    """Run all six rules. Returns issues in a stable order (rule, then entity)."""
    issues: list[ValidationIssue] = []
    issues.extend(_rule_1_counter_dogma_attribution(catalog))
    issues.extend(_rule_2_case_references_well_formed(catalog))
    issues.extend(_rule_3_ids_unique(catalog))
    issues.extend(_rule_4_numbers_unique_and_sequential(catalog))
    issues.extend(_rule_5_v01_priority_not_stub(catalog))
    issues.extend(_rule_6_final_verdict_has_all_fields(catalog))
    issues.sort(key=lambda i: (i.rule, i.entity, i.message))
    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)


# ---------------------------------------------------------------------------
# Rule 1 — counter_dogmas must carry attribution
# ---------------------------------------------------------------------------


def _rule_1_counter_dogma_attribution(
    catalog: Catalog,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    for d in catalog.dogmas:
        cds = d.raw.get("counter_dogmas") or []
        for idx, cd in enumerate(cds):
            if not isinstance(cd, dict):
                out.append(
                    ValidationIssue(
                        rule=1,
                        severity="error",
                        entity=f"dogma:{d.id}",
                        message=f"counter_dogmas[{idx}] is not a mapping: {cd!r}",
                    )
                )
                continue
            attr = cd.get("attribution")
            if not attr or not str(attr).strip():
                name = cd.get("name", f"<index {idx}>")
                out.append(
                    ValidationIssue(
                        rule=1,
                        severity="error",
                        entity=f"dogma:{d.id}",
                        message=(
                            f"counter_dogma '{name}' has no `attribution` "
                            "(rule 1 — honesty-bug)"
                        ),
                    )
                )
    return out


# ---------------------------------------------------------------------------
# Rule 2 — case references have a known shape
# ---------------------------------------------------------------------------


def _rule_2_case_references_well_formed(
    catalog: Catalog,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    for d in catalog.dogmas:
        for field_name in ("failure_cases", "success_cases"):
            value = d.raw.get(field_name)
            if value is None:
                continue
            out.extend(_check_case_value(d, field_name, value))
    return out


def _check_case_value(
    d: DogmaRef, field_name: str, value
) -> list[ValidationIssue]:
    """A case field is valid iff it's (a) a known marker string, or
    (b) a list of mappings."""
    entity = f"dogma:{d.id}"
    if isinstance(value, str):
        if value in CASE_MARKERS:
            return []
        return [
            ValidationIssue(
                rule=2,
                severity="error",
                entity=entity,
                message=(
                    f"{field_name}: unknown marker {value!r}. "
                    f"Allowed: {sorted(CASE_MARKERS)} or a list of entries."
                ),
            )
        ]
    if isinstance(value, list):
        issues: list[ValidationIssue] = []
        for i, item in enumerate(value):
            if not isinstance(item, dict):
                issues.append(
                    ValidationIssue(
                        rule=2,
                        severity="error",
                        entity=entity,
                        message=(
                            f"{field_name}[{i}] must be a mapping "
                            f"with title/source_url/summary, got {type(item).__name__}"
                        ),
                    )
                )
                continue
            if not item.get("title"):
                issues.append(
                    ValidationIssue(
                        rule=2,
                        severity="warning",
                        entity=entity,
                        message=f"{field_name}[{i}] is missing `title`",
                    )
                )
        return issues
    return [
        ValidationIssue(
            rule=2,
            severity="error",
            entity=entity,
            message=(
                f"{field_name}: expected str marker or list, "
                f"got {type(value).__name__}"
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Rule 3 — ids unique across dogmas + candidates
# ---------------------------------------------------------------------------


def _rule_3_ids_unique(catalog: Catalog) -> list[ValidationIssue]:
    seen: dict[str, list[str]] = {}
    for d in catalog.dogmas:
        seen.setdefault(d.id, []).append(f"dogma §{d.number}")
    for c in catalog.candidates:
        seen.setdefault(c.id, []).append("candidate")
    return [
        ValidationIssue(
            rule=3,
            severity="error",
            entity="catalog",
            message=(
                f"id {id_!r} reused across entries: {', '.join(owners)}"
            ),
        )
        for id_, owners in seen.items()
        if len(owners) > 1
    ]


# ---------------------------------------------------------------------------
# Rule 4 — numbers unique AND sequential from 1
# ---------------------------------------------------------------------------


def _rule_4_numbers_unique_and_sequential(
    catalog: Catalog,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    by_number: dict[int, list[str]] = {}
    for d in catalog.dogmas:
        by_number.setdefault(d.number, []).append(d.id)
    for n, ids in by_number.items():
        if len(ids) > 1:
            out.append(
                ValidationIssue(
                    rule=4,
                    severity="error",
                    entity="catalog",
                    message=f"number §{n} reused: {ids}",
                )
            )
    nums_sorted = sorted(by_number.keys())
    expected = list(range(1, len(nums_sorted) + 1))
    if nums_sorted != expected:
        missing = set(expected) - set(nums_sorted)
        extra = set(nums_sorted) - set(expected)
        out.append(
            ValidationIssue(
                rule=4,
                severity="error",
                entity="catalog",
                message=(
                    "dogma numbers are not a continuous 1..N sequence. "
                    f"Got {nums_sorted}. Missing: {sorted(missing)}. "
                    f"Extra/out-of-range: {sorted(extra)}."
                ),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Rule 5 — v01_priority implies status != stub
# ---------------------------------------------------------------------------


def _rule_5_v01_priority_not_stub(
    catalog: Catalog,
) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            rule=5,
            severity="error",
            entity=f"dogma:{d.id}",
            message=(
                f"v01_priority is true but status is 'stub' — "
                "priority dogmas must be at least 'draft'."
            ),
        )
        for d in catalog.dogmas
        if d.v01_priority and d.status == "stub"
    ]


# ---------------------------------------------------------------------------
# Rule 6 — honest_verdict.status: final ⇒ all narrative fields present
# ---------------------------------------------------------------------------


def _rule_6_final_verdict_has_all_fields(
    catalog: Catalog,
) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    for d in catalog.dogmas:
        v = d.raw.get("honest_verdict")
        if not isinstance(v, dict):
            continue
        if v.get("status") != "final":
            continue
        missing: list[str] = []
        for key in ("follow_when", "break_when"):
            items = v.get(key)
            if not items or not isinstance(items, list) or not any(
                str(x).strip() for x in items
            ):
                missing.append(key)
        main = v.get("main_signal")
        if not main or not str(main).strip():
            missing.append("main_signal")
        if missing:
            out.append(
                ValidationIssue(
                    rule=6,
                    severity="error",
                    entity=f"dogma:{d.id}",
                    message=(
                        "honest_verdict.status is 'final' but these fields "
                        f"are empty/missing: {missing}"
                    ),
                )
            )
    return out
