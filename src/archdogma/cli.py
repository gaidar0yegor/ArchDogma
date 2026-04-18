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
@click.pass_context
def probe(ctx: click.Context, target: Path, function_name: str | None) -> None:
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

    result = probe_function(target, function_name)
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
# dogmas — list catalog entries (naive, pending ADR-002)
# ---------------------------------------------------------------------------


@main.command(help="List dogmas from the catalog. [v0.1: naive, see ADR-002.]")
@click.option(
    "--catalog",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to DOGMAS.md. Defaults to project root.",
)
def dogmas(catalog: Path | None) -> None:
    """List dogma catalog entries.

    v0.1 implementation: naive grep of `## N. Name` headings from DOGMAS.md.
    Machine-readable format is ADR-002 (pending).
    """
    if catalog is None:
        catalog = _find_dogmas_md()
    if catalog is None or not catalog.exists():
        click.echo("DOGMAS.md not found. Pass --catalog <path>.", err=True)
        sys.exit(1)

    click.echo(f"=== Dogma catalog ({catalog}) ===")
    in_code_fence = False
    for line in catalog.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if (
            line.startswith("## ")
            and not line.startswith("## Догмы-кандидаты")
            and not line.startswith("## Как контрибьютить")
        ):
            click.echo(line[3:].strip())


def _find_dogmas_md() -> Path | None:
    """Look for DOGMAS.md in the current working dir and a few ancestors."""
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        p = candidate / "DOGMAS.md"
        if p.exists():
            return p
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
    click.echo("Catalog links: (none — Probe→Catalog wiring ships with ADR-002)")


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
    console.print(
        "[dim]Catalog links: none yet — Probe→Catalog wiring ships with ADR-002.[/dim]"
    )


if __name__ == "__main__":
    main()
