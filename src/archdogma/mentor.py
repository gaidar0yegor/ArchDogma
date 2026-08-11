"""The `explain` command — the catalog as a mentor, one entry at a time.

`dogmas` lists, `search` finds, `scan` flags. None of them answers the
question a junior actually has when a tag fires or a rule gets quoted at
them in review: *where does this rule come from, who has it burned, and
when does it stop applying?* That answer has been sitting in the catalog
since ADR-002 — this command is just the first surface that serves one
entry whole.

The rendering order is deliberate and is the argument structure the
catalog wants people to internalise:

    what the rule says → where it came from → the conditions under which
    it fails → who paid for it (with sources) → what the counter-position
    is (with attribution) → when to follow, when to break, and the one
    signal that tells you it is already breaking.

Plain output per ADR-001: sections and one fact per line, no box drawing,
screen-reader parseable. `--speak` mirrors `probe --speak`: additive,
never the only channel, never crashes over a missing audio device.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from archdogma.catalog.loader import (
    Catalog,
    CandidateRef,
    CatalogError,
    DogmaRef,
    load_catalog,
)


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------
#
# One positional TARGET, resolved in a fixed priority order rather than
# guessed at: exact dogma id, exact candidate id, dogma number ("3" or
# "§3"), detector tag name (via tag_index — may map to several entries,
# all are shown), then title substring as a last resort. The order is
# documented in --help; ambiguity is only possible at the tag and
# substring stages, and both return everything they matched rather than
# silently picking a winner.


def resolve_target(
    catalog: Catalog, target: str
) -> list[DogmaRef | CandidateRef]:
    """Resolve TARGET to catalog entries, best interpretation first."""
    t = target.strip().lower()

    by_id = {d.id: d for d in catalog.dogmas}
    if t in by_id:
        return [by_id[t]]

    candidates_by_id = {c.id: c for c in catalog.candidates}
    if t in candidates_by_id:
        return [candidates_by_id[t]]

    number = t.lstrip("§#")
    if number.isdigit():
        hits = [d for d in catalog.dogmas if d.number == int(number)]
        if hits:
            return hits

    if t in catalog.tag_index:
        return list(catalog.tag_index[t])

    return [
        d
        for d in catalog.dogmas
        if t in d.title.lower() or t in d.id
    ] + [
        c
        for c in catalog.candidates
        if t in c.title.lower() or t in c.id
    ]


def suggestions(catalog: Catalog, target: str, limit: int = 6) -> list[str]:
    """Nearby ids and tags for the not-found message."""
    from difflib import get_close_matches

    pool = (
        [d.id for d in catalog.dogmas]
        + [c.id for c in catalog.candidates]
        + list(catalog.tag_index)
    )
    return get_close_matches(target.lower(), pool, n=limit, cutoff=0.4)


# ---------------------------------------------------------------------------
# Plain rendering
# ---------------------------------------------------------------------------


def _section(lines: list[str], title: str) -> None:
    lines.append("")
    lines.append(f"{title}:")


def render_entry(entry: DogmaRef | CandidateRef) -> str:
    """Render one catalog entry as the full mentor explanation."""
    raw = entry.raw or {}
    lines: list[str] = []

    if isinstance(entry, DogmaRef):
        lines.append(f"§{entry.number}. {entry.title}  [{entry.status}]")
    else:
        lines.append(f"{entry.title}  [candidate]")
    lines.append(f"id: {entry.id}")

    # Dogmas have a `definition` — the rule as its adherents state it.
    # Candidates have a `note` — a description of a pattern, not a creed —
    # and labelling one as the other would misrepresent the entry.
    if raw.get("definition"):
        _section(lines, "The rule as preached")
        lines.append(f"  {raw['definition'].strip()}")
    elif raw.get("note"):
        _section(lines, "What it is")
        lines.append(f"  {raw['note'].strip()}")

    origin = raw.get("origin")
    if origin:
        _section(lines, "Where it comes from")
        lines.append(f"  {origin.strip()}")

    conditions = raw.get("failure_conditions")
    if conditions:
        _section(lines, "Conditions under which it fails")
        for c in conditions:
            lines.append(f"  - {c}")

    cases = raw.get("failure_cases")
    if isinstance(cases, list) and cases:
        _section(lines, "Who paid for it")
        for case in cases:
            if not isinstance(case, dict):
                continue
            lines.append(f"  * {case.get('title', '(untitled)')}")
            url = case.get("source_url")
            lines.append(
                f"    source: {url if url else '(no URL — first-party account or print source, per catalog convention)'}"
            )
            summary = (case.get("summary") or "").strip()
            if summary:
                for para_line in summary.splitlines():
                    lines.append(f"    {para_line.strip()}")
            lines.append("")
        while lines and lines[-1] == "":
            lines.pop()
    elif cases == "need_postmortems":
        _section(lines, "Who paid for it")
        lines.append(
            "  No sourced case yet — the catalog says so rather than stretching "
            "one to fit. Have one? Open an issue with the `postmortem` label."
        )

    counters = raw.get("counter_dogmas")
    if counters:
        _section(lines, "The counter-position")
        for cd in counters:
            if not isinstance(cd, dict):
                continue
            name = cd.get("name", "")
            attribution = cd.get("attribution", "")
            lines.append(f"  * {name} — {attribution}")
            thesis = (cd.get("thesis") or "").strip()
            if thesis:
                lines.append(f"    {thesis}")

    verdict = raw.get("honest_verdict") or {}
    if isinstance(verdict, dict):
        follow = verdict.get("follow_when")
        if follow:
            _section(lines, "Follow it when")
            for f in follow:
                lines.append(f"  - {f}")
        break_when = verdict.get("break_when")
        if break_when:
            _section(lines, "Break it when")
            for b in break_when:
                lines.append(f"  - {b}")
        signal = verdict.get("main_signal")
        if signal:
            _section(lines, "The signal it is already breaking")
            lines.append(f"  {signal.strip()}")

    sources = raw.get("sources")
    if sources:
        _section(lines, "Sources")
        for s in sources:
            if not isinstance(s, dict):
                continue
            url = s.get("url")
            lines.append(f"  - {s.get('title', '')}")
            if url:
                lines.append(f"    {url}")

    if entry.related_tags:
        _section(lines, "Detected by")
        lines.append(f"  {', '.join(entry.related_tags)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Spoken summary
# ---------------------------------------------------------------------------
#
# Same contract as probe --speak: a compressed spoken version, additive to
# the printed text, never the only channel. The spoken form is the verdict,
# not the bibliography — a listener wants the rule, one case, and the main
# signal, not URLs read aloud.


def spoken_summary(entry: DogmaRef | CandidateRef) -> str:
    raw = entry.raw or {}
    parts: list[str] = [entry.title.rstrip(".") + "."]

    definition = raw.get("definition") or raw.get("note")
    if definition:
        parts.append(definition.strip().rstrip(".") + ".")

    cases = raw.get("failure_cases")
    if isinstance(cases, list) and cases:
        first = cases[0]
        if isinstance(first, dict) and first.get("title"):
            parts.append("Documented failure: " + first["title"].rstrip(".") + ".")
        extra = len(cases) - 1
        if extra > 0:
            parts.append(
                f"{extra} more sourced case{'s' if extra > 1 else ''} in the catalog."
            )

    verdict = raw.get("honest_verdict") or {}
    if isinstance(verdict, dict) and verdict.get("main_signal"):
        parts.append("Main signal: " + verdict["main_signal"].strip())

    return " ".join(parts)


# ---------------------------------------------------------------------------
# The command
# ---------------------------------------------------------------------------


@click.command(
    "explain",
    help=(
        "Explain one catalog entry in full — the rule, its origin, who it "
        "broke, and when to break it. TARGET is a dogma id (dry), a "
        "candidate id (bus-factor), a dogma number (4), a detector tag "
        "(circular-import), or a title fragment."
    ),
)
@click.argument("target")
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["plain", "json"]),
    default="plain",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--speak",
    "speak_flag",
    is_flag=True,
    default=False,
    help="Additionally speak a short summary aloud (additive, never required).",
)
def explain(
    target: str,
    catalog_path: Path | None,
    output_format: str,
    speak_flag: bool,
) -> None:
    """Explain one dogma, candidate, or detector tag from the catalog."""
    import json as _json

    try:
        catalog = load_catalog(catalog_path)
    except CatalogError as e:
        click.echo(f"Catalog error: {e}", err=True)
        sys.exit(1)

    entries = resolve_target(catalog, target)
    if not entries:
        click.echo(f"Nothing in the catalog matches '{target}'.", err=True)
        near = suggestions(catalog, target)
        if near:
            click.echo("Did you mean: " + ", ".join(near), err=True)
        sys.exit(1)

    if output_format == "json":
        payload = {
            "target": target,
            "matches": [
                {"id": e.id, "kind": e.kind, **(e.raw or {})} for e in entries
            ],
        }
        click.echo(_json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        for i, entry in enumerate(entries):
            if i:
                click.echo("\n" + "=" * 72 + "\n")
            click.echo(render_entry(entry))
        if len(entries) > 1:
            click.echo(
                f"\n'{target}' matched {len(entries)} entries; all shown.",
                err=True,
            )

    if speak_flag:
        from archdogma.voice.speak import speak as _speak

        _speak(spoken_summary(entries[0]))
