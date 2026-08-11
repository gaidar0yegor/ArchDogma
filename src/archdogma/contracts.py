"""Architecture contracts over the import graph — weighted by history.

import-linter proved the shape: declare which imports are allowed, fail CI
on the rest. What no contract tool does is tell you which violation to fix
FIRST. A layering breach in a file nobody has touched since 2021 and one
in this quarter's churn-hotspot are the same boolean to a contract checker
— and very different work items to a team.

So every violation here carries the violating module's history alongside
it: commits, age, churn percentile. Facts, not a severity score — the
project does not invent severities (see the SARIF note in report.py), it
attaches the evidence and lets the gate be the user's choice:

    --fail on any violation           (import-linter-compatible behaviour)
    --fail-only-active                (fail only violations whose importer
                                       changed within --active-days)

Contract types, deliberately the smallest useful subset of import-linter's
five (their semantics, credited — see README):

    forbidden      modules in `source` may not import modules in `forbidden`
    layers         ordered high → low; lower layers may not import higher
    independence   listed subtrees may not import each other

Config lives in pyproject.toml under [tool.archdogma], read with stdlib
tomllib — no new dependency:

    [[tool.archdogma.contracts]]
    name = "probe does not know the cli exists"
    type = "forbidden"
    source = ["archdogma.probe"]
    forbidden = ["archdogma.cli"]

Matching is by module prefix: "pkg.sub" covers "pkg.sub" and everything
under it. An empty contracts list is reported as "no contracts", never as
"all contracts hold" — the difference between a passed check and a check
that never ran is this catalog's oldest theme.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import click

from archdogma.probe.graph import ImportGraph


@dataclass(frozen=True)
class Contract:
    name: str
    type: str  # forbidden | layers | independence
    source: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    layers: tuple[str, ...] = ()  # ordered high -> low
    modules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Violation:
    contract: str
    importer: str
    imported: str
    reason: str
    # History facts for the IMPORTER — the file someone must now edit.
    commits: int | None = None
    days_since_change: int | None = None
    churn_percentile: float | None = None


@dataclass(frozen=True)
class ContractReport:
    contracts: tuple[Contract, ...]
    violations: tuple[Violation, ...]
    history_available: bool = False

    @property
    def checked(self) -> int:
        return len(self.contracts)


class ContractConfigError(ValueError):
    """Malformed [tool.archdogma] contracts — always fatal, never guessed at."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _as_tuple(raw: object, where: str) -> tuple[str, ...]:
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return tuple(raw)
    raise ContractConfigError(f"{where}: expected a string or list of strings")


def load_contracts(pyproject: Path) -> list[Contract]:
    """Read [[tool.archdogma.contracts]] from a pyproject.toml.

    Missing file or missing table means "no contracts declared" — an empty
    list, which callers must report as such. Malformed entries raise: a
    contract that silently fails to parse is a gate that silently opened.
    """
    if not pyproject.exists():
        return []
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    raw = data.get("tool", {}).get("archdogma", {}).get("contracts", [])
    if not isinstance(raw, list):
        raise ContractConfigError("[tool.archdogma].contracts must be an array of tables")

    out: list[Contract] = []
    for i, entry in enumerate(raw):
        where = f"contracts[{i}]"
        if not isinstance(entry, dict):
            raise ContractConfigError(f"{where}: expected a table")
        name = entry.get("name") or f"contract #{i + 1}"
        ctype = entry.get("type")
        if ctype == "forbidden":
            contract = Contract(
                name=name,
                type=ctype,
                source=_as_tuple(entry.get("source"), f"{where}.source"),
                forbidden=_as_tuple(entry.get("forbidden"), f"{where}.forbidden"),
            )
        elif ctype == "layers":
            layers = _as_tuple(entry.get("layers"), f"{where}.layers")
            if len(layers) < 2:
                raise ContractConfigError(f"{where}: layers needs at least two entries")
            contract = Contract(name=name, type=ctype, layers=layers)
        elif ctype == "independence":
            modules = _as_tuple(entry.get("modules"), f"{where}.modules")
            if len(modules) < 2:
                raise ContractConfigError(f"{where}: independence needs at least two modules")
            contract = Contract(name=name, type=ctype, modules=modules)
        else:
            raise ContractConfigError(
                f"{where}: unknown type {ctype!r} (forbidden | layers | independence)"
            )
        out.append(contract)
    return out


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------


def _in_subtree(module: str, prefixes: tuple[str, ...]) -> str | None:
    """The prefix that claims `module`, or None. Longest match wins so a
    module under both "pkg" and "pkg.sub" is attributed to the closer root."""
    best: str | None = None
    for p in prefixes:
        if module == p or module.startswith(p + "."):
            if best is None or len(p) > len(best):
                best = p
    return best


def check_contract(contract: Contract, graph: ImportGraph) -> list[Violation]:
    violations: list[Violation] = []
    for importer, targets in sorted(graph.edges.items()):
        for imported in targets:
            reason = _violates(contract, importer, imported)
            if reason:
                violations.append(
                    Violation(
                        contract=contract.name,
                        importer=importer,
                        imported=imported,
                        reason=reason,
                    )
                )
    return violations


def _violates(contract: Contract, importer: str, imported: str) -> str | None:
    if contract.type == "forbidden":
        if _in_subtree(importer, contract.source) and _in_subtree(
            imported, contract.forbidden
        ):
            return f"{importer} may not import {imported}"
        return None

    if contract.type == "layers":
        src_layer = _in_subtree(importer, contract.layers)
        dst_layer = _in_subtree(imported, contract.layers)
        if src_layer is None or dst_layer is None or src_layer == dst_layer:
            return None
        # layers are ordered high -> low; an import from a lower layer up
        # into a higher one is the breach (import-linter semantics).
        if contract.layers.index(src_layer) > contract.layers.index(dst_layer):
            return (
                f"{src_layer} is below {dst_layer} in the declared layering "
                f"and may not import upward"
            )
        return None

    if contract.type == "independence":
        src = _in_subtree(importer, contract.modules)
        dst = _in_subtree(imported, contract.modules)
        if src and dst and src != dst:
            return f"{src} and {dst} are declared independent"
        return None

    return None


def annotate_with_history(
    violations: list[Violation], graph: ImportGraph, history
) -> list[Violation]:
    """Attach the importer's change history to each violation.

    The importer, not the imported: the violation lives in the importing
    file, and that file's churn is what prices the fix.
    """
    if history is None:
        return violations
    out: list[Violation] = []
    for v in violations:
        node = graph.modules.get(v.importer)
        if node is None:
            out.append(v)
            continue
        entry = history.for_path(node.path)
        rank = history.churn_percentile(node.path)
        out.append(
            Violation(
                contract=v.contract,
                importer=v.importer,
                imported=v.imported,
                reason=v.reason,
                commits=entry.commits if entry else None,
                days_since_change=history.days_since_change(node.path),
                churn_percentile=round(rank, 3) if rank is not None else None,
            )
        )
    return out


def run_contracts(
    root: Path,
    config_path: Path | None = None,
    use_history: bool = True,
    excludes: tuple[str, ...] = (),
) -> ContractReport:
    """Load contracts, build the graph once, check everything."""
    from archdogma.history import load_history
    from archdogma.probe.graph import build_graph
    from archdogma.probe.scanner import collect_python_files

    pyproject = config_path or (root / "pyproject.toml")
    contracts = load_contracts(pyproject)
    if not contracts:
        return ContractReport(contracts=(), violations=())

    graph = build_graph(list(collect_python_files(root, excludes)))
    history = load_history(root) if use_history else None

    violations: list[Violation] = []
    for contract in contracts:
        violations.extend(check_contract(contract, graph))
    violations = annotate_with_history(violations, graph, history)

    return ContractReport(
        contracts=tuple(contracts),
        violations=tuple(violations),
        history_available=history is not None,
    )


# ---------------------------------------------------------------------------
# CLI — registered onto the main group from cli.py, same as explain/mcp
# ---------------------------------------------------------------------------


def _is_active(v: Violation, active_days: int) -> bool | None:
    """True/False when history answers; None when it cannot."""
    if v.days_since_change is None:
        return None
    return v.days_since_change <= active_days


@click.command(
    "contracts",
    help=(
        "Check declared architecture contracts (forbidden / layers / "
        "independence) against the import graph, with each violation "
        "priced by the importing file's git history."
    ),
)
@click.argument(
    "path",
    type=click.Path(exists=True, file_okay=False, readable=True, path_type=Path),
    default=Path("."),
    required=False,
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="pyproject.toml holding [tool.archdogma].contracts. Default: PATH/pyproject.toml.",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    metavar="PATTERN",
    help="Glob pattern (relative to PATH) to exclude. Repeatable.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["plain", "json"]),
    default="plain",
    show_default=True,
)
@click.option(
    "--history/--no-history",
    "use_history",
    default=True,
    show_default=True,
    help="Annotate violations with the importer's git history.",
)
@click.option(
    "--fail-only-active",
    is_flag=True,
    default=False,
    help=(
        "Exit non-zero only for violations whose importing file changed "
        "within --active-days. Violations in dormant files are still "
        "REPORTED — this gates the exit code, it does not hide findings. "
        "Without usable git history every violation counts as active: "
        "unknown is not dormant."
    ),
)
@click.option(
    "--active-days",
    type=int,
    default=90,
    show_default=True,
    help="A file counts as active if it changed within this many days.",
)
@click.option(
    "--fail/--no-fail",
    "fail_on_violations",
    default=True,
    show_default=True,
)
def contracts_command(
    path: Path,
    config_path: Path | None,
    exclude: tuple[str, ...],
    output_format: str,
    use_history: bool,
    fail_only_active: bool,
    active_days: int,
    fail_on_violations: bool,
) -> None:
    """Check architecture contracts, history-priced."""
    import json as _json

    try:
        report = run_contracts(
            path, config_path=config_path, use_history=use_history, excludes=exclude
        )
    except ContractConfigError as e:
        click.echo(f"Contract config error: {e}", err=True)
        sys.exit(2)

    if not report.contracts:
        message = (
            "No contracts declared ([tool.archdogma].contracts in pyproject.toml). "
            "Nothing was checked — this is not a pass."
        )
        if output_format == "json":
            click.echo(_json.dumps({"contracts": 0, "checked": False, "note": message}))
        else:
            click.echo(message)
        return

    gating = [
        v
        for v in report.violations
        if not fail_only_active or _is_active(v, active_days) in (True, None)
    ]

    if output_format == "json":
        click.echo(
            _json.dumps(
                {
                    "contracts": [c.name for c in report.contracts],
                    "history_available": report.history_available,
                    "violations": [
                        {
                            "contract": v.contract,
                            "importer": v.importer,
                            "imported": v.imported,
                            "reason": v.reason,
                            "importer_commits": v.commits,
                            "importer_days_since_change": v.days_since_change,
                            "importer_churn_percentile": v.churn_percentile,
                            "active": _is_active(v, active_days),
                        }
                        for v in report.violations
                    ],
                    "gating_violations": len(gating),
                },
                indent=2,
            )
        )
    else:
        for v in report.violations:
            click.echo(f"\n[{v.contract}] {v.reason}")
            click.echo(f"  {v.importer} -> {v.imported}")
            if v.commits is not None:
                age = f"{v.days_since_change}d ago" if v.days_since_change is not None else "?"
                pct = (
                    f", top {(1 - v.churn_percentile) * 100:.0f}% churn"
                    if v.churn_percentile is not None
                    else ""
                )
                active = _is_active(v, active_days)
                label = "ACTIVE" if active else "dormant"
                click.echo(
                    f"  importer history: {v.commits} commits, last change {age}{pct} — {label}"
                )
            elif report.history_available:
                click.echo("  importer history: not in git history")
        click.echo(
            f"\n{len(report.contracts)} contract(s) · {len(report.violations)} "
            f"violation(s)"
            + (
                f" · {len(gating)} gating (--fail-only-active, {active_days}d)"
                if fail_only_active
                else ""
            )
        )
        if not report.history_available and use_history:
            click.echo(
                "  No usable git history — violations cannot be priced; "
                "all count as active.",
                err=True,
            )

    if fail_on_violations and gating:
        sys.exit(1)
