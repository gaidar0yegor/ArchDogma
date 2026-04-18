"""End-to-end test that Probe picks up catalog links from tags.

This is the ADR-002 smoke: `probe_function` + loaded catalog →
`ProbeResult.catalog_links` populated when a detector fires on a tag
that the catalog claims via `related_tags`.
"""

from __future__ import annotations

from pathlib import Path

from archdogma.catalog.loader import Catalog, CandidateRef, DogmaRef, load_catalog
from archdogma.probe.walker import CatalogLink, probe_function

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "long_function_sample.py"


def _synth_catalog() -> Catalog:
    """Build a tiny catalog that maps long-function → one candidate,
    without touching the real YAML. Keeps this test independent of catalog edits."""
    candidate = CandidateRef(
        id="synthetic-god-class",
        title="Synthetic God Class",
        related_tags=("long-function", "god-function"),
    )
    dogma = DogmaRef(
        id="synthetic-deep",
        number=99,
        title="Synthetic Deep Nesting Dogma",
        status="draft",
        related_tags=("deep-nesting",),
    )
    # The real Catalog class builds tag_index from its inputs; reproduce that.
    from collections import defaultdict

    idx: dict[str, list] = defaultdict(list)
    for t in candidate.related_tags:
        idx[t].append(candidate)
    for t in dogma.related_tags:
        idx[t].append(dogma)
    return Catalog(
        schema_version=1,
        dogmas=(dogma,),
        candidates=(candidate,),
        tag_index={k: tuple(v) for k, v in idx.items()},
    )


# ---------------------------------------------------------------------------
# Probe without catalog → empty links (not None, not an error)
# ---------------------------------------------------------------------------


def test_probe_without_catalog_has_no_links() -> None:
    result = probe_function(FIXTURE, "long_and_deep")
    assert result is not None
    assert result.tags, "fixture should still trigger detectors"
    assert result.catalog_links == ()


# ---------------------------------------------------------------------------
# Probe with catalog → real links
# ---------------------------------------------------------------------------


def test_probe_with_catalog_resolves_long_function_link() -> None:
    cat = _synth_catalog()
    result = probe_function(FIXTURE, "long_and_deep", catalog=cat)
    assert result is not None
    link_tags = {link.tag_name for link in result.catalog_links}
    assert "long-function" in link_tags
    assert "deep-nesting" in link_tags


def test_probe_catalog_links_carry_entry_shape() -> None:
    cat = _synth_catalog()
    result = probe_function(FIXTURE, "long_and_deep", catalog=cat)
    assert result is not None

    deep_links = [link for link in result.catalog_links if link.tag_name == "deep-nesting"]
    assert len(deep_links) == 1
    assert isinstance(deep_links[0], CatalogLink)
    assert deep_links[0].entry_kind == "dogma"
    assert deep_links[0].entry_number == 99
    assert deep_links[0].entry_id == "synthetic-deep"

    lf_links = [link for link in result.catalog_links if link.tag_name == "long-function"]
    assert len(lf_links) == 1
    assert lf_links[0].entry_kind == "candidate"
    assert lf_links[0].entry_number is None  # candidates have no §-number
    assert lf_links[0].entry_id == "synthetic-god-class"


# ---------------------------------------------------------------------------
# Tag with no catalog entry → not in links (silent miss is correct)
# ---------------------------------------------------------------------------


def test_tag_not_in_catalog_is_silently_omitted() -> None:
    """Synth catalog doesn't claim 'nonexistent-tag' → no link for that tag."""
    cat = _synth_catalog()
    result = probe_function(FIXTURE, "long_and_deep", catalog=cat)
    assert result is not None
    for link in result.catalog_links:
        assert link.tag_name in ("deep-nesting", "long-function")


# ---------------------------------------------------------------------------
# End-to-end with the REAL catalog (deliberate coupling — regression guard)
# ---------------------------------------------------------------------------


def test_real_catalog_links_long_function_to_god_class_candidate() -> None:
    """If somebody ever drops `long-function` from God Class candidate's
    related_tags, this test breaks loudly. That's the whole point of wiring."""
    cat = load_catalog()
    result = probe_function(FIXTURE, "long_and_deep", catalog=cat)
    assert result is not None
    lf_links = [link for link in result.catalog_links if link.tag_name == "long-function"]
    assert lf_links, "real catalog must claim long-function via god-class candidate"
    assert any(link.entry_id == "god-class" for link in lf_links)
