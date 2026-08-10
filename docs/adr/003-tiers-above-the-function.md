# ADR-003: Tiers above the function — import graph and change history

## Status

Accepted — 2026-08-11.

## Context

Every detector through v0.2.1 was function- or class-scoped. That was the right
place to start, and it has a hard ceiling that the catalog had already been
documenting against itself:

    clean-architecture:  related_tags: []  # module-level concern, not
                                           # detectable from a single function
    solid:               related_tags: []  # class/module level; not detectable
                                           # from single function AST

Two of twelve dogmas carried an explicit note that the tool could not reach
them. That is honest, and it is also a statement that the analysis level was
wrong for the question. "Do dependencies point inward?" is not a property of
any function. Neither is "which file does everything rest on?"

Meanwhile the package description shipped on PyPI advertised circular imports,
god modules, and tight coupling — three things no detector touched. The gap
between what the tool claimed and what it did had become large enough to
produce a false claim in the shopfront of a project whose stated purpose is
sourcing claims.

Three options were considered:

1. **Stay at function level; delete the false claims.** Cheapest, and leaves
   the catalog permanently unable to reach its own module-level dogmas.
2. **Add a module tier only.** Answers layering and coupling questions.
   Cannot distinguish a file that is load-bearing from a file that is large.
3. **Add a module tier and a history tier.** Answers both, at the cost of a
   dependency on git and a class of finding that is not reproducible from
   the working tree alone.

## Decision

Option **(3)**, with the tiers kept explicitly separate rather than merged
into one "analysis" surface.

- **Tier 2** is the import graph: `probe/graph.py`, detectors in
  `probe/tags/tier2.py`. Pure working-tree analysis, stdlib only.
- **Tier 3** is Tier 2 crossed with `git log`: `history.py`, detectors in
  `probe/tags/tier3.py`. Requires a work tree.

Tier 3 has its own detector registry and its own `(name, graph, history)`
signature rather than widening the Tier 2 protocol with an optional argument.
Tier 3 is the tier that can be switched off, and that ought to be visible in
the type rather than hidden in a `None` check inside a shared loop.

### Consequences that are deliberate

**No history means no tags, never "no findings".** A shallow clone, a tarball
download, a CI checkout with `--depth 1` — all yield `history=None`, and every
Tier 3 detector returns nothing. The JSON payload carries
`history.available: false` with a reason, and the plain output prints
`Tier 3 skipped` to stderr. A consumer that cannot distinguish "no
load-bearing walls" from "we never looked" will report the second as the
first, so the distinction is made structural.

**"Now" is the newest commit, not wall-clock time.** Ages are measured from
`RepoHistory.as_of`. Scanning the same commit gives the same answer next year.
Wall-clock would make every threshold a slowly drifting one and every CI
assertion eventually false for reasons unrelated to the code.

**Churn is a percentile, not a count.** Twenty-three commits describes a
different situation in a two-month project than in a ten-year one. An absolute
threshold would not transfer between repositories, and a detector that only
works on codebases the size of the one it was tuned on is a tuned constant
pretending to be a finding.

**A tag on a dogma is a pointer, not a verdict.** `hub-module` on DRY finds
the shape of the catalog's own QuackNet case. It does not prove any particular
hub is a wrong abstraction — a legitimate core is also a hub.
`load-bearing-wall` describes both a mature utility that stopped changing
because it was finished and a module the team routes around out of fear; the
detail text says so and a test holds it there.

**`microservices` stays empty.** Tier 2 sees one repository's imports. The
failure in the Segment case lives in deployment topology and shared databases.
Adding a tag here would be a guess wearing a tag name. The reason is written
into `catalog/dogmas.yaml` so that the emptiness reads as a decision rather
than as a backlog item.

### Deviation from ADR-001

ADR-001 listed `gitpython` as an optional dependency for Tier 3, with tags
named `old-code` and `high-churn`. Neither survived contact:

- **No gitpython.** One `git log --numstat` call through `subprocess` is the
  whole integration. A library that wraps git would have added a dependency,
  a version constraint and an import cost for a single command whose output
  format we parse anyway. The `[git]` extra has been removed from
  `pyproject.toml` — it installed a package nothing imports.
- **Different tag names.** `old-code` describes the measurement; the finding
  is the combination of age *and* afferent coupling, which is why the tag is
  `load-bearing-wall`. `high-churn` became `churn-hotspot` for the same
  reason — churn alone is not the signal, churn crossed with size is.

### Known limits, recorded rather than discovered later

- Renames are not followed. `git log --follow` is per-path and would turn one
  subprocess call into one per file; a file renamed last month therefore looks
  one month old.
- Dynamic imports are invisible to the graph. A codebase using
  `importlib.import_module` looks less coupled than it is. Tier 1's
  `dynamic-magic` tag is the honest hint that the graph is incomplete there.
- Temporal coupling shipped after the first draft of this ADR. Two filters
  carry it, and both are load-bearing rather than tuning: commits touching
  more than 30 files contribute no pairs, or one formatter run couples the
  entire repository and the strongest "hidden relationships" in the report
  become an artifact of a tool run; and files under 5 revisions are excluded,
  or two files sharing their only commit score a perfect 1.0. Pairs are also
  restricted to `.py` files, which bounds the pair count and costs nothing —
  nothing downstream can ask about a file that is not a module.

## Alternatives rejected

**Merging Tier 2 and Tier 3 into one module-level pass.** Simpler surface, but
it makes the git dependency implicit. A user running in a tarball would get a
quieter report with no indication that a whole class of finding had been
skipped.

**Inferring service boundaries from directory layout to give `microservices` a
detector.** Directory layout is not deployment topology. This would have been
the most-requested detector and the least defensible one.
