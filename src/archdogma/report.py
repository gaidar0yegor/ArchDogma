"""Machine-readable serialisation of findings — the agent-facing surface.

`scan` and `modules` both emit JSON, and both are consumed by something
that was not in the room when the code was written: a CI job, or an agent
auditing an unfamiliar repository. That consumer needs what a reviewer
would get, not what a linter would. A bare list of tag names is linter
output — "god-module at line 1" carries no more meaning than "C0301 line
too long".

So every tag carries the ids of the catalog entries that claim it, and the
entries themselves are emitted once at the top level with the part that
actually decides an argument: the conditions under which the dogma stops
working, and the signal that it already has.

Normalised rather than inlined. The same dogma is claimed by several tags,
and repeating its `break_when` list at every occurrence would multiply the
payload without adding information.
"""

from __future__ import annotations

from archdogma.catalog.loader import Catalog


def tags_payload(tags: tuple, links: tuple) -> list[dict]:
    """Serialise tags, attaching the catalog entry ids that claim each one."""
    by_tag: dict[str, list[str]] = {}
    for link in links:
        ids = by_tag.setdefault(link.tag_name, [])
        if link.entry_id not in ids:
            ids.append(link.entry_id)
    return [
        {
            "name": t.name,
            "line": t.line,
            "col": t.col,
            "detail": t.detail,
            "dogmas": by_tag.get(t.name, []),
        }
        for t in tags
    ]


def _collect_entry_ids(payload: object) -> set[str]:
    """Every catalog entry id referenced anywhere in an emitted payload."""
    found: set[str] = set()
    if isinstance(payload, dict):
        if isinstance(payload.get("dogmas"), list):
            found.update(str(x) for x in payload["dogmas"])
        for value in payload.values():
            found |= _collect_entry_ids(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= _collect_entry_ids(item)
    return found


def _entry_payload(entry: object) -> dict:
    """Flatten one catalog entry to the fields an agent can reason with."""
    raw = getattr(entry, "raw", {}) or {}
    verdict = raw.get("honest_verdict") or {}
    out: dict = {
        "kind": getattr(entry, "kind", "dogma"),
        "title": getattr(entry, "title", ""),
    }
    number = getattr(entry, "number", None)
    if number is not None:
        out["number"] = number
    status = getattr(entry, "status", None)
    if status is not None:
        out["status"] = status
    for key in ("definition", "note"):
        if raw.get(key):
            out[key] = raw[key]
    if isinstance(verdict, dict):
        for key in ("follow_when", "break_when", "main_signal"):
            if verdict.get(key):
                out[key] = verdict[key]
    cases = raw.get("failure_cases")
    if isinstance(cases, list):
        out["failure_cases"] = [
            {"title": c.get("title"), "source_url": c.get("source_url")}
            for c in cases
            if isinstance(c, dict)
        ]
    sources = raw.get("sources")
    if isinstance(sources, list):
        out["sources"] = [
            {"title": s.get("title"), "url": s.get("url")}
            for s in sources
            if isinstance(s, dict)
        ]
    return out


def catalog_payload(
    payload: object, catalog: Catalog | None, note: str | None = None
) -> dict:
    """Top-level catalog block holding only the entries actually referenced.

    `note` lets callers state provenance decisions out loud — e.g. that a
    scanned project's own catalog was used INSTEAD of the bundled one, so
    tags the project catalog does not claim carry no context here. Silent
    context loss is the failure mode; the note is the fix.
    """
    if catalog is None:
        return {
            "loaded": False,
            "note": (
                "No catalog found. Tags are reported without their conditions, "
                "which makes this output a linter report."
            ),
            "entries": {},
        }
    wanted = _collect_entry_ids(payload)
    by_id = {e.id: e for e in (*catalog.dogmas, *catalog.candidates)}
    out = {
        "loaded": True,
        "updated": catalog.updated,
        "entries": {
            eid: _entry_payload(by_id[eid]) for eid in sorted(wanted) if eid in by_id
        },
    }
    if note:
        out["note"] = note
    return out



_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/"
    "sarif-2.1/schema/sarif-schema-2.1.0.json"
)
_REPO_URL = "https://github.com/gaidar0yegor/ArchDogma"


def sarif_payload(findings: list[dict], version: str) -> dict:
    """Wrap findings into a SARIF 2.1.0 log.

    `findings` items: {rule_id, message, file, line, dogmas: [ids]}.
    SARIF exists so aggregators (CodeRabbit-style platforms, GitHub code
    scanning) can ingest us without bespoke glue. Every result is level
    "warning" — this tool ships signals with context, not severities, and
    inventing a severity scale here would claim a precision the detectors
    do not have.
    """
    from pathlib import PurePath
    from urllib.parse import quote

    def _uri(raw: str) -> str:
        # SARIF 3.4.3: artifactLocation.uri must be a valid URI reference.
        # A raw filesystem path with spaces is not one. Relative paths stay
        # relative (percent-encoded); absolute paths become file:// URIs.
        posix = PurePath(raw).as_posix()
        if PurePath(raw).is_absolute():
            return "file://" + quote(posix, safe="/")
        return quote(posix, safe="/")

    rules: dict[str, dict] = {}
    results: list[dict] = []
    for f in findings:
        rule_id = f["rule_id"]
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "shortDescription": {"text": rule_id},
                "helpUri": f"{_REPO_URL}/blob/main/DOGMAS.md",
            },
        )
        message = f["message"]
        if f.get("dogmas"):
            message += " [catalog: " + ", ".join(f["dogmas"]) + "]"
        results.append(
            {
                "ruleId": rule_id,
                "level": "warning",
                "message": {"text": message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": _uri(f["file"])},
                            "region": {"startLine": max(1, int(f["line"]))},
                        }
                    }
                ],
            }
        )
    return {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ArchDogma",
                        "version": version,
                        "informationUri": _REPO_URL,
                        "rules": sorted(rules.values(), key=lambda r: r["id"]),
                    }
                },
                "results": results,
            }
        ],
    }


def scan_findings_for_sarif(file_results: list) -> list[dict]:
    """Flatten Tier 1 FileScanResults into sarif_payload's finding shape."""
    out: list[dict] = []
    for fr in file_results:
        if getattr(fr, "parse_error", None) is not None:
            continue
        for r in fr.results:
            links_by_tag: dict[str, list[str]] = {}
            for link in r.catalog_links:
                ids = links_by_tag.setdefault(link.tag_name, [])
                if link.entry_id not in ids:
                    ids.append(link.entry_id)
            for t in r.tags:
                out.append(
                    {
                        "rule_id": t.name,
                        "message": f"{r.function_name}: {t.detail}",
                        "file": str(fr.file),
                        "line": t.line,
                        "dogmas": links_by_tag.get(t.name, []),
                    }
                )
    return out


def module_findings_for_sarif(modules: list) -> list[dict]:
    """Flatten Tier 2/3 ModuleResults into sarif_payload's finding shape."""
    out: list[dict] = []
    for m in modules:
        links_by_tag: dict[str, list[str]] = {}
        for link in m.catalog_links:
            ids = links_by_tag.setdefault(link.tag_name, [])
            if link.entry_id not in ids:
                ids.append(link.entry_id)
        for t in m.tags:
            out.append(
                {
                    "rule_id": t.name,
                    "message": f"{m.name}: {t.detail}",
                    "file": str(m.file),
                    "line": t.line,
                    "dogmas": links_by_tag.get(t.name, []),
                }
            )
    return out


def history_payload(result: object) -> dict:
    """Describe whether Tier 3 ran, and under what limits.

    Emitted even when history is absent. A consumer that cannot distinguish
    "no load-bearing walls" from "we never looked" will report the second as
    the first.
    """
    history = getattr(result, "history", None)
    if history is None:
        return {
            "available": False,
            "reason": (
                "No usable git history: not a work tree, a shallow clone (detected "
                "and refused rather than served truncated), or git "
                "unavailable. Tier 3 tags were not evaluated — their "
                "absence is not evidence."
            ),
        }
    return {
        "available": True,
        "as_of": history.as_of,
        "files_with_history": len(history.files),
        "follows_renames": history.follows_renames,
        "note": (
            "Ages are measured from the newest commit in the repository, not "
            "wall-clock time, so the same commit always scores the same."
        ),
    }


