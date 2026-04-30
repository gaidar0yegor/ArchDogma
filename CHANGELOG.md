# Changelog

All notable changes are recorded here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[SemVer](https://semver.org/), but on pre-alpha the major/minor aren't stable yet:
breaking changes are allowed in any release before `0.1.0`.

## [Unreleased]

### Added
- **Voice Mode (Phase 1 realignment, Day-1 accessibility debt closed)**.
  Voice was promised in README as a Day-1 feature and stayed `NotImplementedError`
  for four commits. Now it works.
  - `src/archdogma/voice/speak.py`: `speak(text) -> bool`. Never throws.
    Backend selection order: native `say` (macOS) → native `espeak-ng` (Linux) →
    `pyttsx3` (Windows / any-OS fallback) → late `espeak-ng` on non-Linux if installed.
    All failures (FileNotFoundError, TimeoutExpired, RuntimeError from pyttsx3 when
    audio driver is absent) are swallowed: returns `False` + one deduplicated line
    to stderr. CLI doesn't crash.
  - CLI: `archdogma probe` gains `--speak` flag. Reads aloud a short summary
    ("Two tags found: long function, too many params. Trust score unknown.").
    Plain-text stdout is byte-identical to running without `--speak` — voice is an
    **additive** channel.
  - Sentence synthesizer (`_synthesize_spoken_summary`): singular/plural,
    numbers up to 10 as words (`One`/`Two`/...`Ten`), ≥11 as digits.
    Kebab-case tags are humanized (`long-function` → "long function"), otherwise
    TTS pronounces the hyphens. Until Phase 2 (Trust Score) the sentence always
    ends with an honest "Trust score unknown." — staying silent would be dishonest.
  - Open question answer #1: `cli.py` builds the string and passes a plain `str`
    to `speak()`. The voice layer knows nothing about `ProbeResult` — dumb sink,
    easy to test, easy to swap backend.
  - Open question answer #2: for Phase 2 git-blame outside a repository →
    `age_median = "unknown"` (not exception, not zero). Honest `unknown` >
    invented metric.
- **ADR-002 renderer + validator (debt closed)**.
  - `src/archdogma/catalog/renderer.py`: `render_catalog(cat) -> str`.
    Deterministic (bytes-identical runs), UTF-8. First line — AUTO-GENERATED banner.
    Stub dogmas get an honest placeholder instead of invented prose.
  - `src/archdogma/catalog/validator.py`: `validate_catalog(cat) ->
    list[ValidationIssue]`. Six rules from ADR-002:
    1. `counter_dogmas[].attribution` must exist (honesty-bug).
    2. `failure_cases` / `success_cases` — valid marker
       (`need_postmortems` / `need_data` / `need_cases`) **or**
       list of `{title, source_url, summary}`.
    3. `id` is unique across `dogmas + candidates`.
    4. `number` is unique **and** continuous from 1.
    5. `v01_priority: true` ⇒ `status != "stub"`.
    6. `honest_verdict.status: "final"` ⇒ non-empty
       `follow_when` + `break_when` + `main_signal`.
  - CLI: `archdogma render-catalog [--output PATH] [--check]` —
    last flag for CI (diff against committed `.md`).
  - CLI: `archdogma validate-catalog` — exit 1 on any error.
  - `DOGMAS.md` is now generated from YAML (first line: AUTO-GENERATED banner).
    Edits go into YAML.
  - `DogmaRef` / `CandidateRef` got `raw: dict` (compare=False, repr=False) —
    renderer and validator work with full YAML without bloating types.
- **ADR-002 wiring (gentle minimum)**: `catalog/dogmas.yaml` is now a live source;
  `src/archdogma/catalog/loader.py` implemented — `DogmaRef`, `CandidateRef`,
  `Catalog` (frozen dataclasses), `tag_index`. Probe now accepts an optional catalog
  and returns `ProbeResult.catalog_links: tuple[CatalogLink, ...]` with
  `tag_name → (entry_id, entry_kind, entry_title, entry_number)`.
  YAML→Markdown renderer and full-validator — still the next milestone.
- **CLI**: `archdogma probe` gains `--catalog PATH`
  (auto-detect by cwd, fallback — warm message to stderr).
  `archdogma dogmas` now reads YAML (not cutting headings from `.md`);
  supports `--include-stubs/--no-stubs` and
  `--include-candidates/--no-candidates`.
- **Tier 1 detector `long-function`** — second tag in registry.
  - SLOC metric: count of physical lines containing at least 1 AST statement.
    Blanks, comment-only lines, leading docstring, and bodies of nested
    `def`/`class` are excluded (those are separate scopes).
  - Multi-line statements correctly count as N lines.
  - Default threshold: 80. Configurable via `threshold` parameter.
  - Source note in tag detail: honestly marked as
    "no research-backed absolute threshold — 50/80/100 heuristics vary by style guide".
  - End-to-end fixture `tests/fixtures/long_function_sample.py::long_and_deep`
    triggers **both** detectors (`deep-nesting` + `long-function`) on one probe —
    regression for TIER1_DETECTORS as registry.
- **Tier 1 detector `god-function`** — third tag in registry.
  - AND semantics of two thresholds: `SLOC ≥ loc_threshold` **AND**
    `branches ≥ branch_threshold`. Either alone — different smells, not this one.
  - McCabe-style branches: `if / elif / for / while / except / case`.
    `with` is sequential, not a branch. Boolean `and/or` not counted.
  - Scope boundary: branches inside nested `def` / `class` belong to them, not
    the outer function (regression covered by test).
  - Defaults: 200 SLOC and 15 branches. Configurable.
  - Honest source note: McCabe (1976) gives branch count;
    "no research-backed absolute god-function threshold exists".
  - Fixture `tests/fixtures/god_function_sample.py::dispatch_everything`
    (209 SLOC, 18 branches) — triggers both `long-function` and
    `god-function`, both link to God Class candidate in catalog.
- **File-level Probe** — class methods and nested functions are now
  addressable (previously only top-level `def`). Dotted qualified names:
  - `foo` — top-level
  - `MyClass.method` — class method
  - `outer.inner` — nested function
  - `MyClass.method.inner` — nested inside method
  - `Outer.Inner.method` — method of nested class
  - `list_all_functions(tree) -> list[DiscoveredFunction]` —
    depth-first source-order walk, returns `qualified_name`,
    `node`, `kind` (`function`/`method`/`nested`), `container`.
  - `find_function(tree, name)` now accepts dotted name.
    Bare `regular_method` does NOT match `Outer.regular_method` —
    partial match would be a surprise and ambiguous.
  - CLI: `archdogma probe FILE` without `--function` groups output
    by kind (Top-level functions / Methods / Nested functions).
  - `--function Outer.method` resolves correctly; not-found message
    lists all addressable names.
  - self/cls rule in `too-many-params` now actually works
    (previously was a future-proof stub — Tier 1 only saw top-level).
- **Tier 1 detector `too-many-params`** — fourth tag in registry.
  - Counts `posonly + args + kwonly` parameters, plus `*args` and `**kwargs`
    as +1 each. Leading `self` / `cls` excluded (future-proof for
    alpha4 class-method probe).
  - Defaulted args count same as required — defaults reduce call noise,
    but not signature complexity.
  - Default threshold: 5. Configurable via `threshold` parameter.
  - Honest source note: Martin (≤3) / pylint R0913 (=5) / Sonar S107 (=7).
    "No research-backed absolute threshold exists".
  - Catalog candidate `long-parameter-list` added with links to
    Fowler "Refactoring" and Martin "Clean Code"; `too-many-params` →
    this candidate via `related_tags`.
  - Fixture `tests/fixtures/too_many_params_sample.py`: `lean` (3, clean),
    `on_the_line` (5, at threshold), `kitchen_sink` (7, with `*args`/`**kwargs`).
- **Authorship**: `pyproject.toml` and `LICENSE` updated —
  Yegor Gaidar, founder / author / executor.

### Dependencies
- `pyyaml >= 6.0` (catalog loader).

### Tests
- +16 units voice speak (`tests/test_voice_speak.py`) —
  backend selection per-platform, subprocess failure modes
  (FileNotFoundError / TimeoutExpired), pyttsx3 import-vs-runtime
  failure, empty/whitespace no-op, warning dedup.
- +13 units CLI speak wiring (`tests/test_cli_speak.py`) —
  sentence synthesis (0/1/N tag forms, humanize, pluralize, numbers),
  `--speak` flag accepted, stdout byte-identical with/without flag,
  backend failure doesn't crash CLI.
- +15 units loader (`tests/test_catalog_loader.py`)
- +5 units Probe↔Catalog wiring (`tests/test_probe_catalog_wiring.py`)
- +17 units god-function (`tests/test_tier1_god_function.py`),
  +1 fixture (`god_function_sample.py`).
- +14 units renderer (`tests/test_catalog_renderer.py`) —
  snapshot determinism, banner shape, section coverage,
  sync-guard against committed `DOGMAS.md`.
- +25 units validator (`tests/test_catalog_validator.py`) —
  positive + negative for all 6 rules.
- +26 units too-many-params (`tests/test_tier1_too_many_params.py`) —
  threshold boundary, posonly/kwonly/vararg/kwarg shape, self/cls
  exclusion, async def, tag shape + honest sources.
- +23 units file-level probe (`tests/test_file_probe.py`) —
  list_all_functions shape, qualified-name resolution, nested
  classes/methods/defs, probe on method with self-exclusion,
  probe on classmethod with cls-exclusion, frozen DiscoveredFunction.
- Total: **196/196 green** (17 deep-nesting + 22 long-function +
  17 god-function + 26 too-many-params + 23 file-probe +
  15 catalog-loader + 14 catalog-renderer + 25 catalog-validator +
  5 probe-wiring + 16 voice-speak + 13 cli-speak + 3 smoke).

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
