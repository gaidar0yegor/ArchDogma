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
from archdogma.agent import mcp_command
from archdogma.contracts import contracts_command
from archdogma.mentor import explain
from archdogma.probe.tags.tier1 import TIER1_DETECTORS
from archdogma.report import catalog_payload, history_payload, tags_payload
from archdogma.probe.walker import (
    DiscoveredFunction,
    ProbeResult,
    list_all_functions,
    parse_file,
    probe_function,
)
from archdogma.voice.speak import speak


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


# The mentor command lives in mentor.py, the MCP command in agent.py; both
# are registered here rather than defined here: cli.py sits one definition
# under its own god-module threshold, and the honest response to that is
# extraction, not exemption.
main.add_command(explain)
main.add_command(mcp_command)
main.add_command(contracts_command)


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
    help=(
        "Qualified function name. Dot-separated: 'foo', 'MyClass.method', "
        "'outer.inner', 'MyClass.method.inner'. "
        "If omitted, lists every addressable function in the file."
    ),
)
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
@click.option(
    "--speak",
    "speak_flag",
    is_flag=True,
    default=False,
    help=(
        "Additionally speak a short summary aloud. "
        "Plain-text stdout is unchanged. Voice is additive — if no TTS "
        "backend is found, the CLI prints a one-line stderr warning and "
        "continues. Never crashes over a missing audio device."
    ),
)
@click.pass_context
def probe(
    ctx: click.Context,
    target: Path,
    function_name: str | None,
    catalog_path: Path | None,
    speak_flag: bool,
) -> None:
    """Analyze one top-level function from a Python file."""
    try:
        tree = parse_file(target)
    except SyntaxError as e:
        click.echo(f"Parse error: {target}:{e.lineno}: {e.msg}", err=True)
        sys.exit(2)

    # No function name → list every addressable function and exit.
    if function_name is None:
        click.echo(f"File: {target}")
        discovered = list_all_functions(tree)
        if not discovered:
            click.echo("No functions found.")
            return
        _print_discovered_functions(discovered)
        click.echo("\nUse --function NAME (or MyClass.method) to probe one.")
        return

    # Catalog is optional — probe works without it, just prints empty links.
    catalog = _try_load_catalog(catalog_path)

    result = probe_function(target, function_name, catalog=catalog)
    if result is None:
        click.echo(
            f"Function '{function_name}' not found in {target}.", err=True
        )
        discovered = list_all_functions(tree)
        if discovered:
            click.echo("Addressable functions in this file:", err=True)
            for df in discovered:
                click.echo(
                    f"- {df.qualified_name}  [{df.kind}]  (line {df.node.lineno})",
                    err=True,
                )
        sys.exit(1)

    _render_result(result, pretty=ctx.obj.get("pretty", False))
    if speak_flag:
        _speak_result(result)


def _print_discovered_functions(discovered: list[DiscoveredFunction]) -> None:
    """Render the function list. Grouped by kind for readability, source order within groups."""
    by_kind: dict[str, list[DiscoveredFunction]] = {
        "function": [],
        "method": [],
        "nested": [],
    }
    for df in discovered:
        by_kind.setdefault(df.kind, []).append(df)

    labels = {
        "function": "Top-level functions",
        "method": "Methods",
        "nested": "Nested functions",
    }
    for kind in ("function", "method", "nested"):
        group = by_kind.get(kind) or []
        if not group:
            continue
        click.echo(f"{labels[kind]}:")
        for df in group:
            click.echo(f"- {df.qualified_name} (line {df.node.lineno})")


# ---------------------------------------------------------------------------
# scan — analyze a whole file or directory
# ---------------------------------------------------------------------------


@main.command(help="Scan a file or directory, probing every function and class.")
@click.argument(
    "path",
    type=click.Path(exists=True, readable=True, path_type=Path),
    default=Path("."),
    required=False,
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    metavar="PATTERN",
    help=(
        "Glob pattern (relative to scan root) to exclude. Repeatable. "
        "Example: --exclude 'tests/**' --exclude '*_pb2.py'."
    ),
)
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
    type=click.Choice(["plain", "json", "sarif"]),
    default="plain",
    show_default=True,
    help="Output format. sarif emits SARIF 2.1.0 for aggregators and code-scanning UIs.",
)
@click.option(
    "--summary/--no-summary",
    default=False,
    help="Print only the summary line, not individual tag details.",
)
@click.option(
    "--fail/--no-fail",
    "fail_on_tags",
    default=True,
    show_default=True,
    help="Exit non-zero when at least one tag is found (useful in CI).",
)
@click.pass_context
def scan(
    ctx: click.Context,
    path: Path,
    exclude: tuple[str, ...],
    catalog_path: Path | None,
    output_format: str,
    summary: bool,
    fail_on_tags: bool,
) -> None:
    """Scan a Python file or directory for Tier 1 tags.

    Probes every function and class in every .py file found.
    Skips __pycache__, .git, venv, dist, build and similar directories.
    """
    import json as _json

    from archdogma.probe.scanner import scan_path

    catalog = _try_load_catalog(catalog_path)
    file_results = list(scan_path(path, catalog=catalog, excludes=exclude))

    if not file_results:
        # Machine formats stay machine-readable even when empty — a human
        # sentence on stdout breaks every parser downstream.
        if output_format == "sarif":
            from archdogma import __version__ as _v
            from archdogma.report import sarif_payload

            click.echo(_json.dumps(sarif_payload([], _v), indent=2))
        elif output_format == "json":
            click.echo(_json.dumps({"scan_root": str(path), "total_files": 0, "files": []}, indent=2))
        else:
            click.echo("No Python files found.")
        return

    error_files = [r for r in file_results if r.parse_error is not None]
    scanned_files = [r for r in file_results if r.parse_error is None]
    total_items = sum(len(r.results) for r in scanned_files)
    total_tags = sum(r.tag_count for r in scanned_files)
    flagged_count = sum(1 for r in scanned_files if r.has_tags)

    if output_format == "sarif":
        from archdogma import __version__ as _v
        from archdogma.report import sarif_payload, scan_findings_for_sarif

        click.echo(
            _json.dumps(
                sarif_payload(scan_findings_for_sarif(file_results), _v), indent=2
            )
        )
        if fail_on_tags and total_tags > 0:
            sys.exit(1)
        return

    if output_format == "json":
        data: dict = {
            "scan_root": str(path),
            "total_files": len(file_results),
            "scanned_files": len(scanned_files),
            "error_files": len(error_files),
            "total_items": total_items,
            "total_tags": total_tags,
            "files": [],
        }
        for fr in file_results:
            if fr.parse_error is not None:
                data["files"].append(
                    {"file": str(fr.file), "parse_error": fr.parse_error}
                )
                continue
            flagged = [r for r in fr.results if r.tags]
            if not flagged:
                continue
            data["files"].append(
                {
                    "file": str(fr.file),
                    "items": [
                        {
                            "name": r.function_name,
                            "line_start": r.line_start,
                            "line_end": r.line_end,
                            "tags": tags_payload(r.tags, r.catalog_links),
                        }
                        for r in flagged
                    ],
                }
            )
        data["catalog"] = catalog_payload(data["files"], catalog)
        click.echo(_json.dumps(data, indent=2))
    else:
        if not summary:
            for fr in file_results:
                if fr.parse_error is not None:
                    click.echo(
                        f"PARSE ERROR  {fr.file}: {fr.parse_error}", err=True
                    )
                    continue
                for result in fr.results:
                    if not result.tags:
                        continue
                    click.echo(
                        f"\n{fr.file}:{result.line_start}  {result.function_name}"
                    )
                    for tag in result.tags:
                        click.echo(f"  [{tag.name}] line {tag.line}: {tag.detail}")
        click.echo(
            f"\nScanned {len(scanned_files)}/{len(file_results)} files"
            f" · {total_items} items"
            f" · {total_tags} tag(s) in {flagged_count} item(s)"
        )
        if error_files:
            click.echo(
                f"  {len(error_files)} file(s) could not be parsed.", err=True
            )

    if fail_on_tags and total_tags > 0:
        sys.exit(1)


@main.command(
    help="Analyse module structure — import graph, coupling, and git history."
)
@click.argument(
    "path",
    type=click.Path(exists=True, readable=True, path_type=Path),
    default=Path("."),
    required=False,
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    metavar="PATTERN",
    help="Glob pattern (relative to scan root) to exclude. Repeatable.",
)
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
    type=click.Choice(["plain", "json", "sarif"]),
    default="plain",
    show_default=True,
    help="Output format. sarif emits SARIF 2.1.0 for aggregators and code-scanning UIs.",
)
@click.option(
    "--history/--no-history",
    "use_history",
    default=True,
    show_default=True,
    help="Use git history for Tier 3 tags. Off gives a working-tree-only result.",
)
@click.option(
    "--all/--flagged-only",
    "show_all",
    default=False,
    show_default=True,
    help="Print every module with its metrics, not only the flagged ones.",
)
@click.option(
    "--fail/--no-fail",
    "fail_on_tags",
    default=True,
    show_default=True,
    help="Exit non-zero when at least one tag is found (useful in CI).",
)
@click.pass_context
def modules(
    ctx: click.Context,
    path: Path,
    exclude: tuple[str, ...],
    catalog_path: Path | None,
    output_format: str,
    use_history: bool,
    show_all: bool,
    fail_on_tags: bool,
) -> None:
    """Run the Tier 2 and Tier 3 detectors over a project.

    Tier 2 is the import graph: cycles, coupling, module size. Tier 3 crosses
    that with `git log`: what is depended upon and never changed, what churns
    hardest, what has one author. Outside a git work tree Tier 3 is silent
    and the output says so.
    """
    import json as _json

    from archdogma.probe.scanner import scan_modules

    catalog = _try_load_catalog(catalog_path)
    result = scan_modules(
        path, catalog=catalog, excludes=exclude, use_history=use_history
    )

    if not result.modules:
        if output_format == "sarif":
            from archdogma import __version__ as _v
            from archdogma.report import sarif_payload

            click.echo(_json.dumps(sarif_payload([], _v), indent=2))
        elif output_format == "json":
            click.echo(
                _json.dumps({"scan_root": str(path), "total_modules": 0, "modules": []}, indent=2)
            )
        else:
            click.echo("No Python files found.")
        return

    graph = result.graph
    edge_count = sum(len(t) for t in graph.edges.values())

    if output_format == "sarif":
        from archdogma import __version__ as _v
        from archdogma.report import module_findings_for_sarif, sarif_payload

        click.echo(
            _json.dumps(
                sarif_payload(module_findings_for_sarif(list(result.flagged)), _v),
                indent=2,
            )
        )
        if fail_on_tags and result.tag_count > 0:
            sys.exit(1)
        return

    if output_format == "json":
        shown = result.modules if show_all else result.flagged
        data: dict = {
            "scan_root": str(path),
            "total_modules": len(result.modules),
            "total_edges": edge_count,
            "total_tags": result.tag_count,
            "cycles": [list(c) for c in graph.cycles],
            "history": history_payload(result),
            "modules": [
                {
                    "name": m.name,
                    "file": str(m.file),
                    "sloc": m.sloc,
                    "def_count": m.def_count,
                    "afferent": m.afferent,
                    "efferent": m.efferent,
                    "instability": round(m.instability, 3),
                    "commits": m.commits,
                    "days_since_change": m.days_since_change,
                    "author_count": m.author_count,
                    "tags": tags_payload(m.tags, m.catalog_links),
                }
                for m in shown
            ],
        }
        if graph.ambiguous_names:
            data["ambiguous_module_names"] = list(graph.ambiguous_names)
        if graph.parse_errors:
            data["parse_errors"] = graph.parse_errors
        data["catalog"] = catalog_payload(data["modules"], catalog)
        click.echo(_json.dumps(data, indent=2))
    else:
        for m in result.modules if show_all else result.flagged:
            click.echo(f"\n{m.file}  {m.name}")
            click.echo(
                f"  Ca={m.afferent} Ce={m.efferent} I={m.instability:.2f}"
                f" · {m.sloc} SLOC · {m.def_count} defs"
                + (
                    f" · {m.commits} commits · last change {m.days_since_change}d ago"
                    if m.commits is not None
                    else ""
                )
            )
            for tag in m.tags:
                click.echo(f"  [{tag.name}] line {tag.line}: {tag.detail}")

        click.echo(
            f"\n{len(result.modules)} modules · {edge_count} internal imports"
            f" · {len(graph.cycles)} cycle(s)"
            f" · {result.tag_count} tag(s) in {len(result.flagged)} module(s)"
        )
        if result.history is None:
            click.echo(
                "  Tier 3 skipped: no usable git history "
                "(not a work tree, shallow clone, or git unavailable).",
                err=True,
            )
        if graph.ambiguous_names:
            click.echo(
                f"  {len(graph.ambiguous_names)} ambiguous module name(s) "
                f"produced no edges: {', '.join(graph.ambiguous_names[:5])}",
                err=True,
            )
        if graph.parse_errors:
            click.echo(
                f"  {len(graph.parse_errors)} file(s) could not be parsed "
                f"and contribute no edges.",
                err=True,
            )

    if fail_on_tags and result.tag_count > 0:
        sys.exit(1)


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
# search — keyword search across dogma catalog
# ---------------------------------------------------------------------------


@main.command(help="Search the dogma catalog by keyword or tag name.")
@click.argument("query")
@click.option(
    "--catalog",
    "catalog_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Path to catalog/dogmas.yaml. Auto-detected from cwd if omitted.",
)
@click.pass_context
def search(ctx: click.Context, query: str, catalog_path: Path | None) -> None:
    """Search the dogma catalog by keyword or tag name."""
    catalog = load_catalog(catalog_path)
    q = query.lower()

    found = []
    for d in sorted(catalog.dogmas, key=lambda x: x.number):
        raw = d.raw
        searchable = " ".join(filter(None, [
            d.title,
            d.id,
            " ".join(d.related_tags),
            raw.get("definition") or "",
            " ".join(raw.get("failure_conditions") or []),
            " ".join(
                item.get("summary", "") if isinstance(item, dict) else ""
                for item in (raw.get("failure_cases") or [])
                if isinstance(item, dict)
            ),
        ])).lower()
        if q in searchable:
            found.append(d)

    if not found:
        click.echo(f"No dogmas found matching '{query}'.")
        return

    for d in found:
        raw = d.raw
        marker = " 🎯" if d.v01_priority else ""
        click.echo(f"§{d.number}. {d.title}{marker}  [{d.status}]")
        if d.related_tags:
            click.echo(f"  Tags: {', '.join(d.related_tags)}")
        defn = raw.get("definition") or ""
        if defn:
            if len(defn) > 120:
                defn = defn[:117] + "..."
            click.echo(f"  {defn}")
        click.echo()


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
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
    except ImportError:
        # rich lives in the `pretty` extra since 0.5.0. Degrading to plain
        # is not a workaround — plain IS the contract (ADR-001); --pretty
        # is the add-on that may be absent.
        click.echo(
            "--pretty needs the 'rich' package (pip install 'archdogma[pretty]'). "
            "Showing plain output.",
            err=True,
        )
        _render_plain(result)
        return

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


# ---------------------------------------------------------------------------
# Voice summary
# ---------------------------------------------------------------------------


def _speak_result(result: ProbeResult) -> None:
    """Synthesize a short spoken summary of a ProbeResult.

    Open-question answer (per user, 2026-04-19): cli.py is the right place to
    construct the spoken string. `speak()` takes plain text — it doesn't need
    to know about ProbeResult shape. Keeps the voice layer dumb and the CLI
    responsible for phrasing. Easy to test, easy to swap backends.

    Trust score is advertised as "unknown" on purpose — Phase 2 of the
    realignment plan delivers it; until then, honesty beats silence.
    """
    sentence = _synthesize_spoken_summary(result)
    speak(sentence)


def _synthesize_spoken_summary(result: ProbeResult) -> str:
    """Turn a ProbeResult into a short English sentence suitable for TTS.

    Examples:
        0 tags   → "No tags detected. Trust score unknown."
        1 tag    → "One tag found: long function. Trust score unknown."
        N tags   → "Two tags found: long function, too many params.
                    Trust score unknown."

    Humanizes kebab-case tag names to natural English so `say` and
    `espeak-ng` don't spell out dashes.
    """
    n = len(result.tags)
    trust_clause = "Trust score unknown."
    if n == 0:
        return f"No tags detected. {trust_clause}"
    word_count = _number_word(n)
    noun = "tag" if n == 1 else "tags"
    humanized = ", ".join(_humanize_tag_name(t.name) for t in result.tags)
    return f"{word_count} {noun} found: {humanized}. {trust_clause}"


_NUMBER_WORDS = {
    1: "One",
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
}


def _number_word(n: int) -> str:
    """Spoken form for small numbers; digits above ten."""
    return _NUMBER_WORDS.get(n, str(n))


def _humanize_tag_name(name: str) -> str:
    """`long-function` → `long function`. TTS-friendly."""
    return name.replace("-", " ")


if __name__ == "__main__":
    main()
