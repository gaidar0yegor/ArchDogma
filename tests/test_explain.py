"""Tests for the `explain` mentor command and its resolution logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from archdogma.catalog.loader import load_catalog
from archdogma.cli import main
from archdogma.mentor import render_entry, resolve_target, spoken_summary

CATALOG = str(Path("catalog/dogmas.yaml"))


@pytest.fixture(scope="module")
def catalog():
    return load_catalog(Path(CATALOG))


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Resolution priority
# ---------------------------------------------------------------------------


def test_resolves_dogma_id(catalog) -> None:
    hits = resolve_target(catalog, "dry")
    assert len(hits) == 1
    assert hits[0].id == "dry"


def test_resolves_candidate_id(catalog) -> None:
    hits = resolve_target(catalog, "bus-factor")
    assert len(hits) == 1
    assert hits[0].kind == "candidate"


def test_resolves_number_with_and_without_section_mark(catalog) -> None:
    plain = resolve_target(catalog, "4")
    marked = resolve_target(catalog, "§4")
    assert plain == marked
    assert plain[0].id == "microservices"


def test_resolves_tag_to_every_claiming_entry(catalog) -> None:
    """A tag claimed by a dogma and a candidate must show both, not pick one."""
    hits = resolve_target(catalog, "circular-import")
    ids = {h.id for h in hits}
    assert "clean-architecture" in ids
    assert "circular-dependency" in ids


def test_resolves_title_fragment(catalog) -> None:
    hits = resolve_target(catalog, "coverage")
    assert any(h.id == "hundred-percent-coverage" for h in hits)


def test_exact_id_wins_over_fragment(catalog) -> None:
    """'kiss' is an id and a plausible fragment; the id must win alone."""
    hits = resolve_target(catalog, "kiss")
    assert len(hits) == 1
    assert hits[0].id == "kiss"


def test_unknown_target_resolves_to_nothing(catalog) -> None:
    assert resolve_target(catalog, "definitely-not-a-thing") == []


def test_resolution_is_case_insensitive(catalog) -> None:
    assert resolve_target(catalog, "DRY")[0].id == "dry"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_contains_the_argument_structure(catalog) -> None:
    """The mentor's order: rule, origin, failures, cases, counters, verdict."""
    text = render_entry(resolve_target(catalog, "dry")[0])
    order = [
        "The rule as preached:",
        "Where it comes from:",
        "Conditions under which it fails:",
        "Who paid for it:",
        "The counter-position:",
        "Follow it when:",
        "Break it when:",
        "The signal it is already breaking:",
    ]
    positions = [text.index(section) for section in order]
    assert positions == sorted(positions)


def test_render_shows_case_sources(catalog) -> None:
    text = render_entry(resolve_target(catalog, "dry")[0])
    assert "https://sandimetz.com" in text


def test_render_null_source_is_labelled_not_blank(catalog) -> None:
    """source_url: null must render as an explicit convention, not silence."""
    text = render_entry(resolve_target(catalog, "dry")[0])
    assert "first-party account or print source" in text


def test_render_empty_cases_stays_honest(catalog) -> None:
    """need_postmortems renders as an explicit gap, not an omitted section."""
    text = render_entry(resolve_target(catalog, "self-documenting-code")[0])
    assert "Who paid for it:" in text
    assert "No sourced case yet" in text


def test_render_candidate_uses_note_label(catalog) -> None:
    """A candidate's note is a description, not a creed."""
    text = render_entry(resolve_target(catalog, "bus-factor")[0])
    assert "What it is:" in text
    assert "The rule as preached:" not in text


def test_render_lists_detecting_tags(catalog) -> None:
    text = render_entry(resolve_target(catalog, "clean-architecture")[0])
    assert "Detected by:" in text
    assert "circular-import" in text


# ---------------------------------------------------------------------------
# Spoken summary
# ---------------------------------------------------------------------------


def test_spoken_summary_carries_verdict_not_bibliography(catalog) -> None:
    spoken = spoken_summary(resolve_target(catalog, "dry")[0])
    assert "Main signal:" in spoken
    assert "http" not in spoken


def test_spoken_summary_counts_additional_cases(catalog) -> None:
    spoken = spoken_summary(resolve_target(catalog, "functional-purity")[0])
    assert "2 more sourced cases" in spoken


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_explain_dogma(runner: CliRunner) -> None:
    result = runner.invoke(main, ["explain", "dry", "--catalog", CATALOG])
    assert result.exit_code == 0
    assert "Who paid for it:" in result.output


def test_cli_explain_by_tag_shows_multiple(runner: CliRunner) -> None:
    result = runner.invoke(
        main, ["explain", "circular-import", "--catalog", CATALOG]
    )
    assert result.exit_code == 0
    assert result.output.count("id: ") == 2
    assert "matched 2 entries" in result.output


def test_cli_unknown_target_exits_nonzero_with_suggestions(
    runner: CliRunner,
) -> None:
    result = runner.invoke(main, ["explain", "solidd", "--catalog", CATALOG])
    assert result.exit_code == 1
    assert "Did you mean" in result.output
    assert "solid" in result.output


def test_cli_json_output_is_the_full_entry(runner: CliRunner) -> None:
    result = runner.invoke(
        main, ["explain", "kiss", "--catalog", CATALOG, "--format", "json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    match = data["matches"][0]
    assert match["id"] == "kiss"
    assert match["kind"] == "dogma"
    assert len(match["failure_cases"]) == 2
    assert match["honest_verdict"]["break_when"]


def test_cli_json_stdout_stays_parseable(runner: CliRunner) -> None:
    result = runner.invoke(
        main, ["explain", "dry", "--catalog", CATALOG, "--format", "json"]
    )
    json.loads(result.stdout)


def test_explain_is_registered_on_main(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert "explain" in result.output
