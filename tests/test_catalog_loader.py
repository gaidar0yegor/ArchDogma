"""Tests for the YAML catalog loader (ADR-002 minimum — loader only).

Renderer and validator land in later milestones; these tests cover just
the contract needed for Probe→Catalog wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archdogma.catalog.loader import (
    CandidateRef,
    Catalog,
    CatalogError,
    DogmaRef,
    default_catalog_path,
    load_catalog,
)


# ---------------------------------------------------------------------------
# Happy path on the real catalog
# ---------------------------------------------------------------------------


@pytest.fixture
def real_catalog_path() -> Path:
    """Path to the project's real catalog/dogmas.yaml."""
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        p = candidate / "catalog" / "dogmas.yaml"
        if p.exists():
            return p
    pytest.fail("catalog/dogmas.yaml not found in project tree")


def test_default_catalog_path_finds_real_file(real_catalog_path: Path) -> None:
    """`default_catalog_path` walks cwd ancestors; project root must be hit."""
    found = default_catalog_path()
    assert found is not None
    assert found.resolve() == real_catalog_path.resolve()


def test_load_real_catalog_shape(real_catalog_path: Path) -> None:
    cat = load_catalog(real_catalog_path)
    assert cat.schema_version == 1
    assert len(cat.dogmas) == 10, "v0.1 seeds ten numbered dogmas"
    assert len(cat.candidates) >= 1


def test_real_catalog_ids_unique(real_catalog_path: Path) -> None:
    cat = load_catalog(real_catalog_path)
    ids = [d.id for d in cat.dogmas] + [c.id for c in cat.candidates]
    assert len(ids) == len(set(ids)), f"duplicate ids: {ids}"


def test_real_catalog_dogma_numbers_unique_and_sequential(
    real_catalog_path: Path,
) -> None:
    cat = load_catalog(real_catalog_path)
    numbers = sorted(d.number for d in cat.dogmas)
    assert numbers == list(range(1, len(numbers) + 1))


def test_real_catalog_has_three_v01_priorities(real_catalog_path: Path) -> None:
    """DOGMAS.md says: DRY / Microservices / TDD are 🎯 v0.1 priorities."""
    cat = load_catalog(real_catalog_path)
    priorities = {d.id for d in cat.dogmas if d.v01_priority}
    assert priorities == {"dry", "microservices", "tdd"}


def test_real_catalog_tag_index_has_long_function(real_catalog_path: Path) -> None:
    """`long-function` → God Class candidate. This is the wire that unblocks
    Probe→Catalog linking — the whole reason ADR-002 exists."""
    cat = load_catalog(real_catalog_path)
    assert "long-function" in cat.tag_index
    entries = cat.tag_index["long-function"]
    assert any(
        e.id == "god-class" and e.kind == "candidate" for e in entries
    ), f"expected god-class candidate, got {entries}"


# ---------------------------------------------------------------------------
# Error modes
# ---------------------------------------------------------------------------


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CatalogError) as exc:
        load_catalog(tmp_path / "nope.yaml")
    assert "not found" in str(exc.value)


def test_non_mapping_root_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just_a_list\n- of_items\n")
    with pytest.raises(CatalogError) as exc:
        load_catalog(bad)
    assert "mapping" in str(exc.value)


def test_unsupported_schema_version_raises(tmp_path: Path) -> None:
    bad = tmp_path / "v999.yaml"
    bad.write_text("schema_version: 999\ndogmas: []\n")
    with pytest.raises(CatalogError) as exc:
        load_catalog(bad)
    assert "v1" in str(exc.value)


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    bad = tmp_path / "broken.yaml"
    bad.write_text("schema_version: 1\ndogmas:\n  - id: ok\n    number: [not, a, number\n")
    with pytest.raises(CatalogError) as exc:
        load_catalog(bad)
    assert "parse error" in str(exc.value).lower()


def test_dogma_missing_required_fields_raises(tmp_path: Path) -> None:
    bad = tmp_path / "missing.yaml"
    bad.write_text(
        "schema_version: 1\n"
        "dogmas:\n"
        "  - id: oops\n"
        "    title: No number and no status\n"
    )
    with pytest.raises(CatalogError) as exc:
        load_catalog(bad)
    assert "number" in str(exc.value) or "status" in str(exc.value)


def test_candidate_missing_required_fields_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad_candidate.yaml"
    bad.write_text(
        "schema_version: 1\n"
        "dogmas: []\n"
        "candidates:\n"
        "  - note: 'candidate without id or title'\n"
    )
    with pytest.raises(CatalogError):
        load_catalog(bad)


# ---------------------------------------------------------------------------
# In-memory synthetic catalog — behaviour without the real file
# ---------------------------------------------------------------------------


def test_tag_index_dedupes_within_entry_but_preserves_cross_entry(
    tmp_path: Path,
) -> None:
    """One tag → multiple entries is valid; dupes within one entry are preserved
    as given (a validator concern, not loader's)."""
    synth = tmp_path / "synth.yaml"
    synth.write_text(
        "schema_version: 1\n"
        "dogmas:\n"
        "  - {id: alpha, number: 1, title: A, status: stub, related_tags: [shared-tag]}\n"
        "  - {id: beta,  number: 2, title: B, status: stub, related_tags: [shared-tag]}\n"
        "candidates:\n"
        "  - {id: gamma, title: G, related_tags: [shared-tag]}\n"
    )
    cat = load_catalog(synth)
    entries = cat.tag_index["shared-tag"]
    assert len(entries) == 3
    ids = {e.id for e in entries}
    assert ids == {"alpha", "beta", "gamma"}


def test_catalog_is_frozen_dataclass(real_catalog_path: Path) -> None:
    """Regression guard: catalog should be immutable after load — it's shared
    read-only across Probe invocations."""
    cat = load_catalog(real_catalog_path)
    assert isinstance(cat, Catalog)
    # DogmaRef / CandidateRef are frozen — mutation raises.
    with pytest.raises((AttributeError, TypeError)):
        cat.dogmas[0].title = "mutated"  # type: ignore[misc]


def test_dogmaref_defaults_are_empty_not_none(tmp_path: Path) -> None:
    """related_tags defaults to empty tuple — never None. Callers iterate
    without a guard."""
    synth = tmp_path / "minimal.yaml"
    synth.write_text(
        "schema_version: 1\n"
        "dogmas:\n"
        "  - {id: x, number: 1, title: X, status: stub}\n"
    )
    cat = load_catalog(synth)
    assert cat.dogmas[0].related_tags == ()
    assert cat.dogmas[0].v01_priority is False
