#!/usr/bin/env python3
"""Audit every source URL in the catalog — the check behind "fetch-verified".

Walks catalog/dogmas.yaml, collects every `source_url` and every
counter-dogma / candidate source link, fetches each one, and reports:

    OK        2xx on the same registrable host
    REDIRECT  2xx but landed on a different host (content may have moved,
              been acquired, or been replaced by a marketing page — verify
              by eye and either annotate the entry or switch to an archive
              capture, the way the Prime Video and Coplien entries do)
    BLOCKED   403/429 — bot wall; verify in a browser or via an archive
    DEAD      4xx/5xx/DNS failure
    NULL      source_url: null — first-party or print, allowed by the rules
              and listed here so the count is visible, not hidden

Exit code 1 if anything is DEAD, so CI or a pre-launch checklist can gate
on it. REDIRECT and BLOCKED are warnings: they need eyes, not automation.

This script exists because "every claim has a source" is only as good as
the last time somebody clicked the sources. Now clicking them is one
command, and the claim is reproducible instead of asserted.

Stdlib only, like the analyzers.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml  # the one non-stdlib import; the catalog is YAML per ADR-002

UA = "Mozilla/5.0 (compatible; archdogma-source-audit)"
TIMEOUT = 25


def registrable_host(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def collect_urls(data: dict) -> list[tuple[str, str | None]]:
    """(where, url) pairs; url None for explicit first-party/print entries."""
    out: list[tuple[str, str | None]] = []

    def from_entry(entry: dict, kind: str) -> None:
        eid = entry.get("id", "?")
        cases = entry.get("failure_cases")
        if isinstance(cases, list):
            for c in cases:
                if isinstance(c, dict):
                    out.append((f"{kind}:{eid} case '{c.get('title', '')[:50]}'", c.get("source_url")))
        for cd in entry.get("counter_dogmas") or []:
            if isinstance(cd, dict) and "source_url" in cd:
                out.append((f"{kind}:{eid} counter '{cd.get('name', '')}'", cd.get("source_url")))
        for src in entry.get("sources") or []:
            if isinstance(src, dict):
                out.append((f"{kind}:{eid} source '{src.get('title', '')[:50]}'", src.get("url")))

    for d in data.get("dogmas") or []:
        from_entry(d, "dogma")
    for c in data.get("candidates") or []:
        from_entry(c, "candidate")
    return out


def check(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            final = resp.geturl()
            if registrable_host(final) != registrable_host(url):
                return "REDIRECT", f"landed on {urllib.parse.urlparse(final).netloc}"
            return "OK", str(resp.status)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            return "BLOCKED", f"HTTP {e.code} (bot wall — verify by eye/archive)"
        return "DEAD", f"HTTP {e.code}"
    except Exception as e:  # DNS, TLS, timeout — all dead for our purposes
        return "DEAD", type(e).__name__


def main() -> int:
    catalog = Path(__file__).resolve().parent.parent / "catalog" / "dogmas.yaml"
    data = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    pairs = collect_urls(data)

    counts = {"OK": 0, "REDIRECT": 0, "BLOCKED": 0, "DEAD": 0, "NULL": 0}
    for where, url in pairs:
        if not url:
            counts["NULL"] += 1
            print(f"NULL      {where}")
            continue
        status, detail = check(url)
        counts[status] += 1
        print(f"{status:9s} {where}\n          {url}  [{detail}]")

    total = sum(counts.values())
    print(
        f"\n{total} sources: {counts['OK']} ok, {counts['REDIRECT']} redirected, "
        f"{counts['BLOCKED']} bot-blocked, {counts['DEAD']} dead, "
        f"{counts['NULL']} first-party/print (no URL by convention)."
    )
    return 1 if counts["DEAD"] else 0


if __name__ == "__main__":
    sys.exit(main())
