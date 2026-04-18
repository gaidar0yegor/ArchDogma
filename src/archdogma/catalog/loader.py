"""Load the machine-readable dogma catalog from `catalog/dogmas.yaml`.

Per ADR-002: YAML is the single source of truth; `DOGMAS.md` is a generated
artifact (renderer ships later). This module is the minimum that unblocks
Probe → Catalog wiring — no validator, no renderer, no Pydantic.

Shape returned from `load_catalog`:

    Catalog(
        schema_version=1,
        dogmas=[DogmaRef(id, number, title, status, v01_priority, related_tags), ...],
        candidates=[CandidateRef(id, title, related_tags), ...],
        tag_index={"long-function": [DogmaRef|CandidateRef, ...], ...},
    )

The `tag_index` is the hot path for Probe→Catalog: pass a detector's tag name
(e.g. "long-function") and get back the list of catalog entries that claim
it via `related_tags`. Candidates are included — they carry sources and are
legitimate catalog links even before promotion to `dogmas`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Support union of DogmaRef and CandidateRef as catalog entries.
# Kept as a sum type via a small marker field on each dataclass (`kind`)
# rather than a common ABC — the fields differ and duck-typing in the CLI
# renderer is cleaner than an interface at this stage.


@dataclass(frozen=True)
class DogmaRef:
    """Lightweight view of one catalog dogma, sufficient for Probe wiring.

    `raw` holds the full dict as parsed from YAML — renderer and validator
    use it to access optional fields (`definition`, `origin`, `counter_dogmas`,
    `honest_verdict`, etc.) without enumerating them here. The dataclass
    itself stays frozen; `raw` is set once at load time.
    """

    id: str
    number: int
    title: str
    status: str  # stub | draft | filled
    v01_priority: bool = False
    related_tags: tuple[str, ...] = ()
    kind: str = "dogma"
    raw: dict = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class CandidateRef:
    """Candidate entry — not yet a full dogma, but can carry related_tags."""

    id: str
    title: str
    related_tags: tuple[str, ...] = ()
    kind: str = "candidate"
    raw: dict = field(default_factory=dict, compare=False, repr=False)


@dataclass(frozen=True)
class Catalog:
    """Loaded catalog plus a pre-built tag→entries index."""

    schema_version: int
    dogmas: tuple[DogmaRef, ...]
    candidates: tuple[CandidateRef, ...]
    tag_index: dict[str, tuple[DogmaRef | CandidateRef, ...]] = field(
        default_factory=dict
    )
    updated: str | None = None  # ISO date string from YAML top-level


class CatalogError(RuntimeError):
    """Raised when the catalog file is missing or malformed."""


def default_catalog_path() -> Path | None:
    """Look for `catalog/dogmas.yaml` in cwd and ancestors.

    Returns None if not found — callers decide whether that's fatal.
    """
    here = Path.cwd()
    for candidate in [here, *here.parents]:
        p = candidate / "catalog" / "dogmas.yaml"
        if p.exists():
            return p
    return None


def load_catalog(path: Path | None = None) -> Catalog:
    """Load and index the YAML catalog.

    Minimal validation — enough to fail loudly on an obviously broken file.
    Schema-level validation (attribution required, unique ids, etc.) is the
    future `archdogma catalog validate` command; keeping them out here keeps
    the loader honest about scope.
    """
    if path is None:
        path = default_catalog_path()
    if path is None or not path.exists():
        raise CatalogError(
            "catalog/dogmas.yaml not found. "
            "Pass an explicit path, or run from a project that has it."
        )

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise CatalogError(f"YAML parse error in {path}: {e}") from e

    if not isinstance(data, dict):
        raise CatalogError(f"Catalog root must be a mapping, got {type(data).__name__}.")

    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise CatalogError(
            f"Unsupported schema_version {schema_version!r}. This loader knows v1."
        )

    dogmas = tuple(_dogma_from_dict(d) for d in (data.get("dogmas") or []))
    candidates = tuple(
        _candidate_from_dict(c) for c in (data.get("candidates") or [])
    )

    # Build tag index. Uniqueness of ids is a validator concern; the index
    # only needs to produce a deterministic list per tag name.
    idx: dict[str, list[DogmaRef | CandidateRef]] = defaultdict(list)
    for d in dogmas:
        for t in d.related_tags:
            idx[t].append(d)
    for c in candidates:
        for t in c.related_tags:
            idx[t].append(c)

    updated = data.get("updated")
    return Catalog(
        schema_version=schema_version,
        dogmas=dogmas,
        candidates=candidates,
        tag_index={k: tuple(v) for k, v in idx.items()},
        updated=str(updated) if updated is not None else None,
    )


def _dogma_from_dict(d: dict) -> DogmaRef:
    missing = [k for k in ("id", "number", "title", "status") if k not in d]
    if missing:
        raise CatalogError(
            f"Dogma {d.get('id', '<unknown>')!r} is missing required fields: {missing}"
        )
    return DogmaRef(
        id=str(d["id"]),
        number=int(d["number"]),
        title=str(d["title"]),
        status=str(d["status"]),
        v01_priority=bool(d.get("v01_priority", False)),
        related_tags=tuple(d.get("related_tags") or ()),
        raw=dict(d),
    )


def _candidate_from_dict(d: dict) -> CandidateRef:
    if "id" not in d or "title" not in d:
        raise CatalogError(
            f"Candidate is missing required fields (id, title): {d!r}"
        )
    return CandidateRef(
        id=str(d["id"]),
        title=str(d["title"]),
        related_tags=tuple(d.get("related_tags") or ()),
        raw=dict(d),
    )


# ---------------------------------------------------------------------------
# Deprecated v0.1-alpha1 shim (kept only to not break imports during alpha2
# migration — delete once no code references it).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DogmaEntry:
    """Legacy flat entry. Prefer `DogmaRef`. Removed in alpha3."""

    number: int
    name: str
    raw_markdown: str


def load_dogmas(path: Path) -> list[DogmaEntry]:
    """Legacy loader. Superseded by `load_catalog`.

    Kept importable so the previous `ImportError` sentinel in tests / scripts
    doesn't become a surprise. Raises immediately to push callers to migrate.
    """
    raise NotImplementedError(
        "load_dogmas(DOGMAS.md) is replaced by load_catalog(catalog/dogmas.yaml). "
        "See ADR-002."
    )
