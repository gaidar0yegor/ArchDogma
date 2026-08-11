"""The agent-facing analysis functions, and the MCP server that serves them.

Coding agents are the newest consumers of this tool and the ones with the
least patience for prose: they act on what they are given, immediately, at
scale. That makes the honesty conventions MORE binding here, not less —
an agent will not read a caveat footnote, so the caveat has to live in the
payload itself (`history.available: false`, "reason", scope notes).

Layout rule: every function here is a plain function taking paths and
returning JSON-serializable dicts. The MCP layer at the bottom is a thin
registration shim. This keeps the logic testable without an MCP client
and keeps the `mcp` SDK import out of every module but this one's
`serve()` — the SDK lives in the `[mcp]` extra, and importing this module
must not require it.

Tool design note: `check_before_refactor` is the tool the others exist to
support. An agent about to edit a file it has never seen asks one
question — "what am I about to break?" — and the answer lives in the
import graph and the git history, not in the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from archdogma.catalog.loader import Catalog, CatalogError, load_catalog
from archdogma.mentor import render_entry, resolve_target, suggestions
from archdogma.probe.scanner import scan_modules, scan_path
from archdogma.report import catalog_payload, history_payload, tags_payload

# Hard ceiling on scanned files for agent calls. An agent pointing this at
# a monorepo root by accident should get a clear refusal, not a five-minute
# stall that it interprets as a hang and retries.
MAX_FILES = 2000


def _load_catalog_or_none(root: Path) -> tuple[Catalog | None, str | None]:
    """(catalog, provenance_note) for the scanned project.

    A project that ships its own `catalog/dogmas.yaml` is describing
    itself, and its claims outrank ours for its own code — but that choice
    must be stated in the payload: tags the project catalog does not claim
    will carry no context, and silent context loss is worse than either
    catalog alone.
    """
    project = root / "catalog" / "dogmas.yaml"
    if project.exists():
        try:
            return load_catalog(project), (
                "Using the scanned project's own catalog "
                f"({project}). Tags it does not claim carry no context here; "
                "the bundled ArchDogma catalog was not consulted."
            )
        except CatalogError:
            pass
    bundled = _bundled_catalog()
    if bundled is not None:
        try:
            return load_catalog(bundled), None
        except CatalogError:
            pass
    return None, None


def _bundled_catalog() -> Path | None:
    """The catalog this installation ships.

    Wheel installs carry a copy at archdogma/_data/dogmas.yaml
    (force-included at build time; repo-root YAML stays the single source
    of truth per ADR-002). Source checkouts resolve the repo-root file —
    with the walk bounded to OUR repo root, identified by its
    pyproject.toml, because an unbounded parent walk once served whatever
    unrelated catalog/dogmas.yaml happened to live above site-packages.
    """
    packaged = Path(__file__).resolve().parent / "_data" / "dogmas.yaml"
    if packaged.exists():
        return packaged

    here = Path(__file__).resolve()
    for parent in here.parents:
        marker = parent / "pyproject.toml"
        if marker.exists():
            if 'name = "archdogma"' not in marker.read_text(encoding="utf-8"):
                return None
            candidate = parent / "catalog" / "dogmas.yaml"
            return candidate if candidate.exists() else None
    return None


def _guard_root(
    project_root: str, excludes: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any] | None]:
    root = Path(project_root).expanduser().resolve()
    if not root.exists():
        return root, {"error": f"path does not exist: {root}"}
    py_count = 0
    if root.is_dir():
        from archdogma.probe.scanner import collect_python_files

        # Count with the caller's excludes applied — the refusal message
        # recommends excludes, so the guard must honour them or the advice
        # is a dead end.
        for py_count, _ in enumerate(
            collect_python_files(root, excludes), start=1
        ):
            if py_count > MAX_FILES:
                return root, {
                    "error": (
                        f"more than {MAX_FILES} Python files under {root}. "
                        "Point at a package directory, not a monorepo root, "
                        "or use excludes."
                    )
                }
    return root, None


# ---------------------------------------------------------------------------
# Tool implementations — plain functions, plain dicts
# ---------------------------------------------------------------------------


def scan_functions(project_root: str, excludes: list[str] | None = None) -> dict:
    """Tier 1: probe every function and class under `project_root`.

    Findings carry the ids of catalog entries that claim each tag; the
    entries themselves ride once in the `catalog` block with break_when
    and main_signal — the part an agent can actually argue with.
    """
    root, err = _guard_root(project_root, tuple(excludes or ()))
    if err:
        return err
    catalog, catalog_note = _load_catalog_or_none(root)
    files = []
    total_tags = 0
    for fr in scan_path(root, catalog=catalog, excludes=tuple(excludes or ())):
        if fr.parse_error is not None:
            files.append({"file": str(fr.file), "parse_error": fr.parse_error})
            continue
        flagged = [r for r in fr.results if r.tags]
        if not flagged:
            continue
        total_tags += sum(len(r.tags) for r in flagged)
        files.append(
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
    payload: dict[str, Any] = {
        "scan_root": str(root),
        "total_tags": total_tags,
        "files": files,
    }
    payload["catalog"] = catalog_payload(payload["files"], catalog, catalog_note)
    return payload


def analyze_modules(
    project_root: str,
    use_history: bool = True,
    excludes: list[str] | None = None,
) -> dict:
    """Tiers 2+3: import graph, coupling, cycles, and git-history signals.

    `history.available: false` means Tier 3 was not evaluated — the absence
    of load-bearing-wall or temporal-coupling tags in that case is not
    evidence of their absence.
    """
    root, err = _guard_root(project_root, tuple(excludes or ()))
    if err:
        return err
    catalog, catalog_note = _load_catalog_or_none(root)
    result = scan_modules(
        root, catalog=catalog, excludes=tuple(excludes or ()), use_history=use_history
    )
    graph = result.graph
    payload: dict[str, Any] = {
        "scan_root": str(root),
        "total_modules": len(result.modules),
        "cycles": [list(c) for c in graph.cycles],
        "history": history_payload(result),
        "modules": [
            {
                "name": m.name,
                "file": str(m.file),
                "sloc": m.sloc,
                "afferent": m.afferent,
                "efferent": m.efferent,
                "instability": round(m.instability, 3),
                "commits": m.commits,
                "days_since_change": m.days_since_change,
                "author_count": m.author_count,
                "tags": tags_payload(m.tags, m.catalog_links),
            }
            for m in result.flagged
        ],
    }
    if graph.parse_errors:
        payload["parse_errors"] = graph.parse_errors
    payload["catalog"] = catalog_payload(payload["modules"], catalog, catalog_note)
    return payload


def explain_dogma(target: str) -> dict:
    """One catalog entry, whole: rule, origin, cases with sources, verdict."""
    catalog_path = _bundled_catalog()
    if catalog_path is None:
        return {"error": "no catalog available in this installation"}
    catalog = load_catalog(catalog_path)
    entries = resolve_target(catalog, target)
    if not entries:
        return {
            "error": f"nothing in the catalog matches '{target}'",
            "suggestions": suggestions(catalog, target),
        }
    return {
        "target": target,
        "matches": [
            {
                "id": e.id,
                "kind": e.kind,
                "rendered": render_entry(e),
                **(e.raw or {}),
            }
            for e in entries
        ],
    }


def check_before_refactor(
    project_root: str, file: str, excludes: list[str] | None = None
) -> dict:
    """Everything the graph and the history know about one file.

    The question an agent should ask before editing code it has never seen:
    who depends on this, when did it last change, whose knowledge is it,
    and what else historically moves when it moves. Facts only — the
    payload states risks, it does not veto. The `verdict` field is a
    summary of the facts above it, never new information.
    """
    root, err = _guard_root(project_root, tuple(excludes or ()))
    if err:
        return err
    catalog, catalog_note = _load_catalog_or_none(root)
    result = scan_modules(
        root, catalog=catalog, excludes=tuple(excludes or ()), use_history=True
    )
    graph = result.graph

    if Path(file).is_absolute():
        target = Path(file)
    elif root.is_file():
        # project_root already IS the file; "root / file" would append one
        # path to another and miss.
        target = root
    else:
        target = root / file
    name = graph.name_for_path(target)
    if name is None:
        hint = "path must point at a .py file under project_root"
        if target.exists() and target.suffix == ".py":
            hint = (
                "the file exists but is not attributable in the graph — "
                "usually an ambiguous bare module name (two files with the "
                "same stem outside packages)"
            )
        return {
            "error": f"{file} is not a module in the scanned graph",
            "hint": hint,
        }

    module = next(m for m in result.modules if m.name == name)
    dependents = list(graph.reverse.get(name, ()))

    # THE detector's floors, imported rather than restated, so this list
    # and the temporal-coupling tag can never quietly disagree again: two
    # files sharing their only commits is not a relationship, and listing
    # it here would teach agents to ignore the field.
    from archdogma.probe.tags.tier3 import (
        DEFAULT_COUPLING_DEGREE,
        DEFAULT_COUPLING_MIN_REVISIONS,
        DEFAULT_COUPLING_MIN_SHARED,
    )

    partners: list[dict[str, Any]] = []
    if result.history is not None:
        entry = result.history.for_path(module.file)
        if entry is not None and entry.commits >= DEFAULT_COUPLING_MIN_REVISIONS:
            for other_path, shared in result.history.partners(entry.path):
                if shared < DEFAULT_COUPLING_MIN_SHARED:
                    continue
                other_entry = result.history.files.get(other_path)
                if (
                    other_entry is None
                    or other_entry.commits < DEFAULT_COUPLING_MIN_REVISIONS
                ):
                    continue
                if (
                    result.history.coupling_degree(entry.path, other_path)
                    < DEFAULT_COUPLING_DEGREE
                ):
                    continue
                other_name = graph.name_for_path(result.history.root / other_path)
                if other_name is None or graph.imports_either_way(name, other_name):
                    continue
                partners.append(
                    {
                        "module": other_name,
                        "shared_commits": shared,
                        "coupling_degree": round(
                            result.history.coupling_degree(entry.path, other_path), 2
                        ),
                    }
                )
            partners.sort(key=lambda x: (-x["coupling_degree"], -x["shared_commits"]))
            partners = partners[:5]

    facts: list[str] = []
    if len(dependents) >= 5:
        facts.append(f"{len(dependents)} modules import this one — changes propagate.")
    if module.days_since_change is not None and module.days_since_change > 365:
        facts.append(
            f"Last change {module.days_since_change} days ago. Old and depended-upon "
            "is either finished or feared; find out which before restructuring."
        )
    # The single-author-hub detector's own gate, imported: one author on a
    # leaf (or in a one-person repo) is unremarkable, and reporting it for
    # every file would bury the cases where it matters.
    from archdogma.probe.tags.tier3 import DEFAULT_BUS_FACTOR_AFFERENT

    if module.author_count == 1 and len(dependents) >= DEFAULT_BUS_FACTOR_AFFERENT:
        facts.append(
            "Single author in its entire history — the context for its decisions "
            "may not be written down anywhere."
        )
    if partners:
        facts.append(
            "Files that historically change with this one, with no import between "
            "them: " + ", ".join(p["module"] for p in partners) + ". Check whether "
            "your change needs to touch them too."
        )
    if result.history is None:
        # An agent will not read a caveat footnote; the caveat is a fact.
        facts.append(
            "Git history was NOT available (no work tree, shallow clone, or "
            "git missing) — age, authorship and co-change were not evaluated. "
            "Their absence above is not evidence."
        )
    if not facts:
        facts.append(
            "No elevated risk signals from the import graph or the history."
        )

    payload: dict[str, Any] = {
        "module": name,
        "file": str(module.file),
        "metrics": {
            "sloc": module.sloc,
            "afferent": module.afferent,
            "efferent": module.efferent,
            "instability": round(module.instability, 3),
            "commits": module.commits,
            "days_since_change": module.days_since_change,
            "author_count": module.author_count,
        },
        "dependents": dependents,
        "dependents_scope": (
            "static imports only — dynamic imports, plugin registries and "
            "string-referenced modules are invisible to this graph"
        ),
        "temporal_partners": partners,
        "tags": tags_payload(module.tags, module.catalog_links),
        "history": history_payload(result),
        "verdict": facts,
    }
    payload["catalog"] = catalog_payload(payload["tags"], catalog, catalog_note)
    return payload


def list_dogmas() -> dict:
    """Catalog index: every dogma and candidate with status and tags."""
    catalog_path = _bundled_catalog()
    if catalog_path is None:
        return {"error": "no catalog available in this installation"}
    catalog = load_catalog(catalog_path)
    return {
        "dogmas": [
            {
                "id": d.id,
                "number": d.number,
                "title": d.title,
                "status": d.status,
                "related_tags": list(d.related_tags),
            }
            for d in sorted(catalog.dogmas, key=lambda x: x.number)
        ],
        "candidates": [
            {"id": c.id, "title": c.title, "related_tags": list(c.related_tags)}
            for c in catalog.candidates
        ],
    }


# ---------------------------------------------------------------------------
# MCP registration — the only part that touches the SDK
# ---------------------------------------------------------------------------


@click.command(
    "mcp",
    help=(
        "Run the MCP server over stdio — architecture analysis and the "
        "dogma catalog as tools for coding agents. Needs: pip install "
        "'archdogma[mcp]'."
    ),
)
def mcp_command() -> None:
    """Click entry point; registered onto the CLI group in cli.py."""
    serve()


def build_server():
    """Configure the MCP server. Split from serve() so tests can inspect
    the registered tools without speaking stdio."""
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as e:
        raise SystemExit(
            "archdogma mcp needs the MCP SDK: pip install 'archdogma[mcp]'"
        ) from e

    from archdogma import __version__

    server = MCPServer(
        name="archdogma",
        version=__version__,
        instructions=(
            "Honest architecture analysis for Python. Findings link to a "
            "catalog of sourced real-world failures — each catalog entry "
            "carries break_when conditions you can weigh, not just a rule "
            "id. history.available=false means git-history tags were not "
            "evaluated; never read their absence as a clean bill. Call "
            "check_before_refactor before editing an unfamiliar file."
        ),
    )

    server.tool(
        name="scan_functions",
        description=(
            "Tier 1 scan: every function and class under project_root, "
            "with catalog context per finding."
        ),
    )(scan_functions)
    server.tool(
        name="analyze_modules",
        description=(
            "Tiers 2+3: import graph, coupling, cycles, git churn, "
            "temporal coupling. Flagged modules only."
        ),
    )(analyze_modules)
    server.tool(
        name="explain_dogma",
        description=(
            "One catalog entry whole: the rule, its origin, sourced failure "
            "cases, counter-positions, when to follow and when to break. "
            "Target: dogma id, tag name, number, or title fragment."
        ),
    )(explain_dogma)
    server.tool(
        name="check_before_refactor",
        description=(
            "Ask before editing an unfamiliar file: who depends on it, when "
            "it last changed, whose knowledge it is, what historically "
            "changes with it. Facts, not a veto."
        ),
    )(check_before_refactor)
    server.tool(
        name="list_dogmas",
        description="Catalog index: dogmas and candidates with their detector tags.",
    )(list_dogmas)

    return server


def serve() -> None:
    """Run the MCP server over stdio. Requires the `[mcp]` extra."""
    build_server().run("stdio")
