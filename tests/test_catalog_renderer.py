"""Tests for YAML→Markdown renderer (ADR-002).

The renderer is a pure function: same input → same output. These tests
pin the contract the CLI `render-catalog --check` depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from archdogma.catalog.loader import (
    Catalog,
    CandidateRef,
    DogmaRef,
    load_catalog,
)
from archdogma.catalog.renderer import AUTOGEN_BANNER, render_catalog


# ---------------------------------------------------------------------------
# Shape of output — banner, header, deterministic
# ---------------------------------------------------------------------------


@pytest.fixture
def real_catalog() -> Catalog:
    return load_catalog()


def test_banner_is_first_line(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    assert out.startswith(AUTOGEN_BANNER.rstrip("\n"))


def test_ends_with_single_newline(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_render_is_deterministic(real_catalog: Catalog) -> None:
    """Two runs of render_catalog on the same input must return byte-identical
    strings. Non-determinism would break CI `--check` permanently."""
    a = render_catalog(real_catalog)
    b = render_catalog(real_catalog)
    assert a == b


def test_render_produces_utf8_russian(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    # Russian text from the catalog must round-trip — no mojibake,
    # no latin-only degradation.
    assert "Каталог догм" in out
    assert "Определение" in out


# ---------------------------------------------------------------------------
# Numbered dogma rendering — order, marker, status
# ---------------------------------------------------------------------------


def test_dogmas_rendered_in_number_order(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    # Pull out the §N lines in appearance order and assert monotonic.
    nums = [
        int(line.split(".", 1)[0].removeprefix("## §"))
        for line in out.splitlines()
        if line.startswith("## §")
    ]
    assert nums == sorted(nums)
    assert nums[0] == 1


def test_v01_priorities_get_marker(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    # DRY, Microservices, TDD (§3, §4, §6) are v0.1 priorities.
    for header in ("§3. DRY", "§4. Microservices", "§6. TDD"):
        assert f"## {header}" in out or any(
            line.startswith(f"## {header}") and "🎯" in line
            for line in out.splitlines()
        )


def test_stub_dogmas_get_placeholder(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    assert "Кейсы и honest verdict пока не заполнены (статус `stub`)" in out


def test_filled_dogma_renders_counter_dogmas(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    # DRY has counter_dogmas: WET, Rule of Three, Wrong Abstraction, AHA.
    assert "WET" in out
    assert "Rule of Three" in out
    assert "Wrong Abstraction" in out
    assert "AHA" in out


def test_counter_dogmas_render_attribution(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    # Attribution is required per rule 1 — renderer must show it, not eat it.
    assert "Sandi Metz" in out
    assert "Martin Fowler" in out


def test_honest_verdict_renders_follow_break_main(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    assert "Следуй догме, когда" in out
    assert "Ломай догму, когда" in out
    assert "Main signal" in out


# ---------------------------------------------------------------------------
# Candidates — they have their own section
# ---------------------------------------------------------------------------


def test_candidates_section_present(real_catalog: Catalog) -> None:
    out = render_catalog(real_catalog)
    assert "## Кандидаты" in out
    assert "God File / God Class" in out


# ---------------------------------------------------------------------------
# Synthetic catalog — isolation from real YAML edits
# ---------------------------------------------------------------------------


def _synth_minimal() -> Catalog:
    """Smallest well-formed catalog the renderer must handle."""
    d = DogmaRef(
        id="x",
        number=1,
        title="Test Dogma",
        status="filled",
        v01_priority=True,
        raw={
            "id": "x",
            "number": 1,
            "title": "Test Dogma",
            "status": "filled",
            "definition": "Just a test.",
            "counter_dogmas": [
                {"name": "Counter", "attribution": "Author 2020", "thesis": "Nope."},
            ],
            "honest_verdict": {
                "status": "final",
                "follow_when": ["always"],
                "break_when": ["never"],
                "main_signal": "it works",
            },
        },
    )
    c = CandidateRef(
        id="cand",
        title="A Candidate",
        raw={"id": "cand", "title": "A Candidate", "note": "untested"},
    )
    return Catalog(
        schema_version=1,
        dogmas=(d,),
        candidates=(c,),
        tag_index={},
        updated="2026-04-18",
    )


def test_synth_minimal_renders_all_sections() -> None:
    out = render_catalog(_synth_minimal())
    assert "## §1. Test Dogma 🎯" in out
    assert "Just a test." in out
    assert "**Counter**" in out
    assert "Author 2020" in out
    assert "## Кандидаты" in out
    assert "A Candidate" in out


def test_empty_candidates_section_omitted() -> None:
    cat = Catalog(
        schema_version=1,
        dogmas=_synth_minimal().dogmas,
        candidates=(),
        tag_index={},
        updated=None,
    )
    out = render_catalog(cat)
    assert "## Кандидаты" not in out


# ---------------------------------------------------------------------------
# CI guard — the committed DOGMAS.md (if any) stays in sync
# ---------------------------------------------------------------------------


def test_committed_dogmas_md_if_present_matches_render(
    real_catalog: Catalog,
) -> None:
    """If the repo checks a DOGMAS.md into git, the renderer must produce
    the same bytes. If no committed file — skip (pre-migration repos)."""
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        md = candidate / "DOGMAS.md"
        if md.exists():
            break
    else:
        pytest.skip("No committed DOGMAS.md to compare against yet.")

    current = md.read_text(encoding="utf-8")
    rendered = render_catalog(real_catalog)
    if current != rendered:
        # Surface the first diverging line so failures are actionable.
        for i, (a, b) in enumerate(
            zip(current.splitlines(), rendered.splitlines()), start=1
        ):
            if a != b:
                pytest.fail(
                    f"DOGMAS.md out of sync at line {i}:\n"
                    f"  committed: {a!r}\n"
                    f"  rendered:  {b!r}\n"
                    "Run: archdogma render-catalog --output DOGMAS.md"
                )
        pytest.fail(
            "DOGMAS.md length differs from rendered output. "
            "Run: archdogma render-catalog --output DOGMAS.md"
        )
