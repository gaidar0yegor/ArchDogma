"""Load dogma entries from DOGMAS.md.

v0.1 is deliberately naive: parse `## N. Name` headings and collect text
until the next heading. No frontmatter, no tags, no machine-readable index.

When ADR-002 lands we swap this out for a structured loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DogmaEntry:
    """One dogma from the catalog (v0.1 shape)."""

    number: int
    name: str
    raw_markdown: str


def load_dogmas(path: Path) -> list[DogmaEntry]:
    """Parse DOGMAS.md into a list of entries.

    Limitations:
    - Ignores non-numbered sections (rules, candidates, contribution guide).
    - Does not extract tag associations — that's ADR-002 work.
    """
    # Body of the parser lands in the next milestone alongside the detectors
    # that actually produce tag → dogma mappings.
    raise NotImplementedError(
        "Catalog loader not implemented yet. See ADR-002 for planned format."
    )
