# Changelog

All notable changes are recorded here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[SemVer](https://semver.org/), but on pre-alpha the major/minor aren't stable yet:
breaking changes are allowed in any release before `0.1.0`.

## [Unreleased]

### Added
- **`temporal-coupling` (Tier 3).** Modules that keep changing in the same
  commit while neither imports the other. The import edge is subtracted on
  purpose — coupling the structure already declares is documented, not hidden.
  Commits touching more than 30 files contribute no pairs, so a formatter run
  cannot couple the whole repository; files with fewer than 5 revisions are
  excluded, so two files sharing their only commit cannot score 1.0.
- New catalog candidate `logical-coupling` (Gall et al., ICSM 1998; Tornhill).
- **CI.** `ci.yml` runs pytest on 3.11/3.12/3.13, validates the catalog,
  asserts `DOGMAS.md` is in sync with its YAML source, and runs both scanners
  over `src/`. Checkout uses `fetch-depth: 0` — a shallow clone would leave
  every file one commit old and silently skip the Tier 3 tests.

### Changed
- `parse_log` returns `(files, as_of, co_changes)`; `RepoHistory` carries
  `co_changes` and a prebuilt `partner_index`. `ImportGraph` gained `by_path`
  and `imports_either_way` so Tier 3 can cross a git path back to a module in
  constant time.

### Removed
- The `[git]` extra. ADR-001 planned gitpython for Tier 3; Tier 3 shipped
  using `subprocess`, so the extra installed a package nothing imports.

## [0.3.0] - 2026-08-11

### Added
- **Tier 2 — module-level analysis.** `probe/graph.py` builds an import graph
  over a project: dotted names resolved through the package chain (so they
  match what `import` would do regardless of scan root), afferent/efferent
  coupling, instability `I = Ce / (Ca + Ce)`, and cycle detection via an
  iterative Tarjan that survives graphs deeper than the recursion limit.
  Detectors: `circular-import`, `hub-module`, `god-module`,
  `unstable-dependency`.
- **Tier 3 — change history.** `history.py` reads `git log --numstat` once and
  crosses it with the import graph. Detectors: `load-bearing-wall` (many
  dependents, no change in years), `churn-hotspot` (large and in the top churn
  percentile of its repository), `single-author-hub` (many dependents, one
  author). Ages are measured from the newest commit in the repository, not
  wall-clock time, so the same commit always scores the same.
- **`archdogma modules [PATH]`** — runs Tier 2 and Tier 3 over a project.
  `--format plain|json`, `--history/--no-history`, `--all/--flagged-only`,
  `--exclude PATTERN`, `--fail/--no-fail`.
- New catalog candidates, all sources link-checked: `circular-dependency`,
  `untouchable-legacy`, `change-hotspot`, `bus-factor`.
- Catalog wiring for dogmas that previously had no detector at any tier:
  `clean-architecture` → `circular-import`, `unstable-dependency`;
  `dry` → `hub-module`; `solid` → `unstable-dependency`.

### Changed
- **JSON output now carries dogma context.** Each tag reports the ids of the
  catalog entries that claim it, and a top-level `catalog` block emits those
  entries once with `break_when`, `main_signal` and source links. Applies to
  both `scan` and `modules`. Previously `scan --format json` dropped catalog
  links entirely, which made the machine-readable output indistinguishable
  from any linter's.
- Payload serialisation moved out of `cli.py` into `report.py`.
- Package description again — see Fixed.

### Fixed
- `scan --format json` and `modules --format json` keep stdout parseable when
  no catalog is found. The "no catalog" note goes to stderr, where it was
  always meant to go.
- **Honesty bug in our own shopfront.** The 0.2.1 description advertised
  "circular imports, god modules, and tight coupling" when no detector in
  `probe/` touched imports, modules or coupling. The CHANGELOG entry below
  repeats the same claim. Both were wrong at the time of writing; as of this
  release the detectors exist and the description is true. Left visible
  rather than rewritten — a catalog of other people's unsourced claims does
  not get to quietly edit its own.

### Known limits
- `microservices` still has no detector, deliberately. Its failure lives in
  deployment topology and shared databases; a Python import graph cannot see
  it, and the reason is now written into the catalog.
- Tier 3 does not follow renames — a file renamed last month looks one month
  old. Merge commits are excluded; formatter commits count as changes.
- `god-module` fires on `archdogma.probe.tags.tier1` in our own source. Left
  standing and asserted in a test.

## [0.2.1] - 2026-07-16

### Changed
- Package description rewritten to match what the tool actually does:
  architecture smells (circular imports, god modules, tight coupling)
  linked to real postmortems.

### Fixed
- `__version__` was stuck at 0.1.0 while the package shipped as 0.2.0 —
  `archdogma --version` now reports the real version.

## [0.2.0] — 2026-05-07

### Added
- **`archdogma scan [PATH]`** — whole-project scanner. Walks every `.py` file,
  runs all Tier 1 detectors on every function and class, and reports tags with
  `file:line` context. Supports `--format plain|json`, `--summary`,
  `--exclude PATTERN` (repeatable fnmatch globs), and `--fail/--no-fail` for
  CI exit codes. JSON output includes `scan_root`, file counts, `total_tags`,
  and per-file items.
- Fixed `detect_god_class()` to accept an optional `classes_in_file` argument,
  aligning it with the `deep-inheritance` protocol used by `probe_class` in
  `walker.py`.
- 19 new tests in `tests/test_scan.py`; total **300 tests, all passing**.

## [0.1.0] — 2026-05-07

### Added
- 11 Tier 1 detectors: `long-function`, `too-many-params`, `nested-loops`,
  `missing-docstring`, `broad-except`, `mutable-default-arg`, `too-many-returns`,
  `if-on-parameter`, `magic-numbers`, `dynamic-magic`, `god-class`, `deep-inheritance`
- 7 dogma entries in catalog: DRY, KISS, SOLID, TDD, YAGNI, Fail Fast, Law of Demeter
- `god-class` and `deep-inheritance` detectors wired into walker via `probe_class`
- 281 tests, all passing

### Changed
- Version bumped from `0.1.0.dev0` to `0.1.0`
- Development status: Pre-Alpha → Alpha
- Author email corrected to `maingaidar@gmail.com`



## [0.1.0-alpha1] — 2026-04-18

First working iteration of the **Probe loop** — AST → detector → tag → CLI.
Not a product, but a proof-of-loop: proving that Variant D architecture
(Probe + Catalog) works on real Python code.

### Added
- **Function Probe**: analysis of one function by name from file.
  - `archdogma probe FILE [--function NAME]` — parses file, finds
    function, runs Tier 1 detectors, prints tags.
  - Without `--function` — lists top-level functions in file.
- **Tier 1 detector `deep-nesting`**.
  - Counts maximum nesting depth of control structures
    (`if`, `for`, `while`, `with`, `try`, `match`).
  - Default threshold: 4. Configurable via `threshold` parameter.
  - `elif` doesn't stack as nesting (human-readable semantics).
  - Source note in tag detail: Cognitive Complexity (Sonarsource 2017) —
    honestly marked as "no research-backed absolute threshold exists".
- **CLI command `archdogma dogmas`**: lists headings from
  `DOGMAS.md`. Skips content inside code fences (templates don't leak).
- **Output**: `--plain` (default, screen-reader friendly per
  [ADR-001](docs/adr/001-cli-first.md)) and `--pretty` (rich Panel + Table).
- **Dogma catalog** `DOGMAS.md`: three v0.1 dogmas fully filled with
  counter-dogmas and honest verdicts —
  [§3 DRY](DOGMAS.md), [§4 Microservices](DOGMAS.md), [§6 TDD](DOGMAS.md).
  Rule: every claim has a source, otherwise `honesty-bug`.
- **AST vocabulary** `AST_TAGS_DRAFT.md`: five-tier classification of
  detection methods; v0.1 locks on Tier 1.
- **ADR-001**: CLI-first choice, Python 3.11+, click + rich + pyttsx3.

### Notes (guarantees and limitations)
- Tests: **17/17 unit + end-to-end on 4 fixtures**.
- Probe works only on top-level `def` / `async def`. Class methods
  and nested functions are not yet addressable.
- Accessibility doctrine: `--plain` is default, not `--pretty`. Color carries
  no information. No spinners or progress bars.
- **Absence of a tag ≠ absence of a problem** — this phrase is printed
  in empty output intentionally.
- `Catalog links: (none)` — honest placeholder until ADR-002 (machine-readable
  catalog schema). Probe↔Catalog wiring — next milestone.

### Known Gaps
- Only one Tier 1 detector. Five more planned (long-function,
  too-many-params, too-many-returns, broad-except, mutable-default-arg).
- §4 Microservices is not detectable at function level — correctly so,
  see README-ladder "Function → File → Module → Service".
- §6 TDD is not purely AST-detectable; Tier 4 (coverage data) —
  future work.

[Unreleased]: https://example.invalid/archdogma/compare/v0.1.0-alpha1...HEAD
[0.1.0-alpha1]: https://example.invalid/archdogma/releases/tag/v0.1.0-alpha1
