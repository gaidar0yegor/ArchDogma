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


def catalog_payload(payload: object, catalog: Catalog | None) -> dict:
    """Top-level catalog block holding only the entries actually referenced."""
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
    return {
        "loaded": True,
        "updated": catalog.updated,
        "entries": {
            eid: _entry_payload(by_id[eid]) for eid in sorted(wanted) if eid in by_id
        },
    }



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
                "No usable git history: not a work tree, a shallow clone, or "
                "git unavailable. Tier 3 tags were not evaluated — their "
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


