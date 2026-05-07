# Changelog

All notable changes are recorded here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[SemVer](https://semver.org/), but on pre-alpha the major/minor aren't stable yet:
breaking changes are allowed in any release before `0.1.0`.

## [Unreleased]

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
