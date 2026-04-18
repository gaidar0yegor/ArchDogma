"""CLI entry point for ArchDogma.

Accessibility contract (per ADR-001):
- Default output is plain structured text, screen-reader parseable.
- `--pretty` opts in to rich formatting for sighted users.
- No color-only information. No spinners. No progress bars by default.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from archdogma import __version__
from archdogma.catalog.loader import Catalog, CatalogError, load_catalog
from archdogma.catalog.renderer import render_catalog
from archdogma.catalog.validator import has_errors, validate_catalog
from archdogma.probe.tags.tier1 import TIER1_DETECTORS
from archdogma.probe.walker import (
    ProbeResult,
    list_top_level_functions,
    parse_file,
    probe_function,
)


# ---------------------------------------------------------------------------
# Root command
# ---------------------------------------------------------------------------


@click.group(
    help=(
        "ArchDogma — honest analysis of one function at a time.\n\n"
        "Status: v0.1 pre-alpha. Tier 1 detectors are landing one by one. "
        "See README.md and AST_TAGS_DRAFT.md."
    )
)
@click.version_option(__version__, prog_name="archdogma")
@click.option(
    "--pretty/--plain",
    default=False,
    help=(
        "Use rich formatting (tables, colors). Default is plain text — "
        "screen-reader friendly per ADR-001."
    ),
)
@click.pass_context
def main(ctx: click.Context, pretty: bool) -> None:
    """Root CLI group."""
    ctx.ensure_object(dict)
    ctx.obj["pretty"] = pretty


# ---------------------------------------------------------------------------
# probe — analyze a single Python function
# ---------------------------------------------------------------------------


@main.command(help="Probe a single Python function.")
@click.argument(
    "target",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "--function",
    "-f",
    "function_name",
    default=None,
    help="Function name to probe. If omitted, lists top-level functions in the file.",
)
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
@click.pass_context
def probe(
    ctx: click.Context,
    target: Path,
    function_name: str | None,
    catalog_path: Path | None,
) -> None:
    """Analyze one top-level function from a Python file."""
    try:
        tree = parse_file(target)
    except SyntaxError as e:
        click.echo(f"Parse error: {target}:{e.lineno}: {e.msg}", err=True)
        sys.exit(2)

    # No function name → list functions and exit.
    if function_name is None:
        click.echo(f"File: {target}")
        funcs = list_top_level_functions(tree)
        if not funcs:
            click.echo("No top-level functions found.")
            return
        click.echo("Top-level functions:")
        for f in funcs:
            click.echo(f"- {f.name} (line {f.lineno})")
        click.echo("\nUse --function NAME to probe one.")
        return

    # Catalog is optional — probe works without it, just prints empty links.
    catalog = _try_load_catalog(catalog_path)

    result = probe_function(target, function_name, catalog=catalog)
    if result is None:
        click.echo(
            f"Function '{function_name}' not found in {target}.", err=True
        )
        funcs = list_top_level_functions(tree)
        if funcs:
            click.echo("Top-level functions defined in this file:", err=True)
            for f in funcs:
                click.echo(f"- {f.name} (line {f.lineno})", err=True)
        sys.exit(1)

    _render_result(result, pretty=ctx.obj.get("pretty", False))


# ---------------------------------------------------------------------------
# dogmas — list catalog entries (from YAML per ADR-002)
# ---------------------------------------------------------------------------


@main.command(help="List dogmas from the catalog (YAML source per ADR-002).")
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
@click.option(
    "--include-stubs/--no-stubs",
    default=True,
    help="Include dogmas with status=stub (default: show all).",
)
@click.option(
    "--include-candidates/--no-candidates",
    default=False,
    help="Include candidate entries (default: dogmas only).",
)
def dogmas(
    catalog_path: Path | None,
    include_stubs: bool,
    include_candidates: bool,
) -> None:
    """List dogma catalog entries from the YAML source."""
    try:
        catalog = load_catalog(catalog_path)
    except CatalogError as e:
        click.echo(f"Catalog error: {e}", err=True)
        sys.exit(1)

    click.echo(f"=== Dogma catalog (schema v{catalog.schema_version}) ===")
    for d in sorted(catalog.dogmas, key=lambda x: x.number):
        if not include_stubs and d.status == "stub":
            continue
        marker = " 🎯" if d.v01_priority else ""
        click.echo(f"§{d.number}. {d.title} [{d.status}]{marker}")

    if include_candidates and catalog.candidates:
        click.echo("")
        click.echo("Candidates (not yet full dogmas):")
        for c in catalog.candidates:
            click.echo(f"- {c.title}  [{c.id}]")


# ---------------------------------------------------------------------------
# render-catalog — YAML → Markdown (ADR-002)
# ---------------------------------------------------------------------------


@main.command("render-catalog", help="Render catalog/dogmas.yaml to Markdown (ADR-002).")
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    default=None,
    help="Where to write DOGMAS.md. If omitted, prints to stdout.",
)
@click.option(
    "--check",
    is_flag=True,
    default=False,
    help=(
        "Don't write anything. Compare rendered output to --output (or project "
        "DOGMAS.md); exit 1 if they differ. For CI."
    ),
)
def render_catalog_cmd(
    catalog_path: Path | None,
    output_path: Path | None,
    check: bool,
) -> None:
    """Render the YAML catalog to Markdown."""
    try:
        catalog = load_catalog(catalog_path)
    except CatalogError as e:
        click.echo(f"Catalog error: {e}", err=True)
        sys.exit(1)
    rendered = render_catalog(catalog)

    if check:
        target = output_path or _default_dogmas_md_path()
        if target is None or not target.exists():
            click.echo(
                f"--check: target {target} does not exist — nothing to compare.",
                err=True,
            )
            sys.exit(1)
        current = target.read_text(encoding="utf-8")
        if current != rendered:
            click.echo(
                f"--check: {target} is out of sync with catalog/dogmas.yaml. "
                "Run `archdogma render-catalog --output ...` to regenerate.",
                err=True,
            )
            sys.exit(1)
        click.echo(f"OK: {target} matches catalog/dogmas.yaml.")
        return

    if output_path is None:
        click.echo(rendered, nl=False)
        return

    output_path.write_text(rendered, encoding="utf-8")
    click.echo(f"Wrote {output_path} ({len(rendered)} bytes).")


def _default_dogmas_md_path() -> Path | None:
    """Project root DOGMAS.md, if we can locate the project."""
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        p = candidate / "DOGMAS.md"
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# validate-catalog — six rules from ADR-002
# ---------------------------------------------------------------------------


@main.command(
    "validate-catalog",
    help="Validate catalog/dogmas.yaml against ADR-002 rules (six rules).",
)
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
def validate_catalog_cmd(catalog_path: Path | None) -> None:
    """Run the six ADR-002 validator rules. Non-zero exit on any error."""
    try:
        catalog = load_catalog(catalog_path)
    except CatalogError as e:
        click.echo(f"Catalog error: {e}", err=True)
        sys.exit(1)

    issues = validate_catalog(catalog)
    if not issues:
        click.echo(
            f"OK: catalog clean ({len(catalog.dogmas)} dogmas, "
            f"{len(catalog.candidates)} candidates). 6/6 rules pass."
        )
        return

    click.echo(f"Found {len(issues)} issue(s):")
    for i in issues:
        click.echo(
            f"  [rule {i.rule}] {i.severity:8s} {i.entity}: {i.message}"
        )
    if has_errors(issues):
        sys.exit(1)


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------


def _try_load_catalog(path: Path | None) -> Catalog | None:
    """Load catalog, but treat absence as non-fatal for `probe`.

    If the user explicitly passed `--catalog` and it's broken, we do exit —
    that's a misconfiguration. If auto-detection just doesn't find one, we
    print a one-line note to stderr and continue without catalog links.
    """
    try:
        return load_catalog(path)
    except CatalogError as e:
        if path is not None:
            click.echo(f"Catalog error: {e}", err=True)
            sys.exit(1)
        click.echo(
            f"Note: {e} Continuing without catalog links.", err=True
        )
        return None


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _render_result(result: ProbeResult, pretty: bool) -> None:
    """Print a ProbeResult in plain or pretty mode.

    Plain mode (default) is screen-reader friendly — simple sections,
    one fact per line, no box drawing.
    """
    if pretty:
        _render_pretty(result)
    else:
        _render_plain(result)


def _render_plain(result: ProbeResult) -> None:
    click.echo("=== Function Probe ===")
    click.echo(f"File: {result.file}")
    click.echo(
        f"Function: {result.function_name} "
        f"(lines {result.line_start}-{result.line_end}, {result.loc} total)"
    )
    click.echo()

    if not result.tags:
        click.echo("No tags from the v0.1 detector set.")
        click.echo(f"v0.1 detectors: {', '.join(n for n, _ in TIER1_DETECTORS)}.")
        click.echo(
            "(Absence of a tag is not absence of a problem. "
            "See AST_TAGS_DRAFT.md for what is not yet detected.)"
        )
        return

    click.echo("Detected tags:")
    for tag in result.tags:
        click.echo(f"- [{tag.name}] at line {tag.line}, col {tag.col}")
        click.echo(f"  {tag.detail}")
    click.echo()

    _render_catalog_links_plain(result)


def _render_catalog_links_plain(result: ProbeResult) -> None:
    if not result.catalog_links:
        if result.tags:
            click.echo(
                "Catalog links: none — no catalog dogma claims these tags yet."
            )
        return
    click.echo("Catalog links:")
    for link in result.catalog_links:
        if link.entry_kind == "dogma" and link.entry_number is not None:
            label = f"§{link.entry_number} {link.entry_title}"
        else:
            label = f"(candidate) {link.entry_title}"
        click.echo(f"- [{link.tag_name}] → {label}  [{link.entry_id}]")


def _render_pretty(result: ProbeResult) -> None:
    """Rich output for sighted users. Kept restrained — no animations."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()
    header = (
        f"[bold]{result.function_name}[/bold] "
        f"([cyan]{result.file}[/cyan], lines {result.line_start}-{result.line_end})"
    )
    console.print(Panel(header, title="Function Probe", expand=False))

    if not result.tags:
        console.print("No tags from the v0.1 detector set.")
        console.print(
            f"v0.1 detectors: {', '.join(n for n, _ in TIER1_DETECTORS)}."
        )
        return

    table = Table(title="Detected tags", show_lines=False)
    table.add_column("Tag", style="bold")
    table.add_column("Location")
    table.add_column("Detail")
    for tag in result.tags:
        table.add_row(tag.name, f"L{tag.line}:{tag.col}", tag.detail)
    console.print(table)

    if not result.catalog_links:
        console.print(
            "[dim]Catalog links: none — no catalog dogma claims these tags yet.[/dim]"
        )
        return

    links = Table(title="Catalog links", show_lines=False)
    links.add_column("Tag", style="bold")
    links.add_column("Entry")
    links.add_column("Kind", style="dim")
    for link in result.catalog_links:
        if link.entry_kind == "dogma" and link.entry_number is not None:
            label = f"§{link.entry_number} {link.entry_title}"
        else:
            label = link.entry_title
        links.add_row(link.tag_name, label, link.entry_kind)
    console.print(links)


if __name__ == "__main__":
    main()
