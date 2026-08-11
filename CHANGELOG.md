# Changelog

All notable changes are recorded here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[SemVer](https://semver.org/), but on pre-alpha the major/minor aren't stable yet:
breaking changes are allowed in any release before `0.1.0`.

## [Unreleased]

### Fixed
- **Pre-launch audit of the v0.1-era catalog entries** — the ones that
  predate the verification pipeline and had never been through it. Found by
  our own adversarial review, fixed before anyone else could: the Segment
  case was dated 2022 (article is July 2018) and called Centrifuge "the
  monolith" (it was the queue infrastructure); the README quoted DHH with a
  sentence that does not appear in his essay, and the TDD entry invented
  Basecamp specifics — both replaced with verbatim quotes and an honest
  "essay, not incident report" label; the same essay was cited for
  Clean-Architecture claims it does not contain (case removed; two verified
  cases remain); the Prime Video source was scrubbed by Amazon (archived
  capture now cited, with a note); the EJB case misdescribed EJB interfaces
  and filed indirection under inheritance (corrected and relabelled); the
  AHA counter-dogma's thesis field held an erratum instead of a thesis; a
  self-attributed counter-dogma cited this catalog's own author as an
  authority (reattributed to the idea's real lineage); and the README
  comparison table claimed tach had "no release since 2025-05" — false
  (0.35.0 shipped 2026-05), corrected and de-snarked.
- README discloses the AI assistance plainly (it was always in the commit
  trailers) and the "fetch-verified" table cell now says what the honesty
  rules already said: external cases fetch-verified, first-party labelled.

### Added
- `tools/verify_sources.py` — audits every source URL in the catalog
  (OK/REDIRECT/BLOCKED/DEAD/NULL), exit 1 on dead links. "Every claim has a
  source" is only as good as the last time somebody clicked the sources;
  now clicking them is one command. Current state: 61 sources, 0 dead.
- GitHub labels `postmortem` and `honesty-bug` now actually exist — the
  README had been pointing contributors at labels nobody had created.

## [0.5.0] - 2026-08-11

### Added
- **`archdogma mcp`** — MCP server over stdio (official SDK via the `[mcp]`
  extra; core stays two-dependency). Five tools: `scan_functions`,
  `analyze_modules`, `explain_dogma`, `list_dogmas`, `check_before_refactor`
  — the pre-flight question for an agent about to edit an unfamiliar file:
  dependents, age, author count, temporal partners. Tool logic is plain
  functions in `agent.py`, testable without an MCP client; the verdict
  facts are gated by the Tier 3 detectors' OWN thresholds, imported rather
  than restated — an earlier draft restated them lower while claiming
  parity, and the pre-merge adversarial review caught exactly that.
  Guarded against monorepo-root scans (explicit refusal, not a stall; the
  guard honours excludes, since its own error message recommends them).
- **Shallow clones are now detected and refused** (`git rev-parse
  --is-shallow-repository`). Previously `load_history`'s docstring promised
  a `--depth 1` clone would not make every file look young — and nothing
  enforced it: a shallow clone returned `available: true` over truncated
  history. Pre-existing 0.4.0 bug, surfaced by the same review.
- **The wheel now ships the catalog** (`archdogma/_data/dogmas.yaml`,
  force-included from the repo-root source of truth). Before this, `pip
  install archdogma` delivered explain/list_dogmas that answered "no
  catalog available in this installation" — the advertised differentiator
  missing from the advertised install path. CI now builds the wheel,
  installs it into a bare venv, and asserts `explain kiss` works.
- When a scanned project ships its own `catalog/dogmas.yaml`, the payload
  now says so (`catalog.note`): its claims outrank ours for its own code,
  and tags it does not claim carry no context — stated, not silent.
- **SARIF 2.1.0 output** (`--format sarif` on `scan` and `modules`) for
  code-scanning UIs and aggregator platforms. All results are `warning`
  level, deliberately: no invented severity scale.
- **Claude Code skill** in `integrations/claude-code/` — teaches an agent
  when to run the pre-flight check and how to read the output honestly
  (`history.available: false` is never a clean bill; tags are pointers,
  not verdicts).

### Changed
- **Core dependencies cut to two** (`click`, `pyyaml`). `rich` moved to the
  `pretty` extra and `pyttsx3` to the `voice` extra. `--pretty` without rich
  degrades to plain output with a pointer to the extra — plain IS the
  accessibility contract (ADR-001), so nothing is lost. Voice on macOS/Linux
  never needed pyttsx3 (native `say`/`espeak-ng`); the extra matters on
  Windows only. The project page's "pure stdlib" claim was false with four
  runtime deps; two-plus-extras makes the honest claim "stdlib analyzers,
  two-dependency core".
- README: positioning statement and a sourced comparison table
  (import-linter, tach, pydeps, CodeScene, repowise) under honesty-bug rules.

## [0.4.0] - 2026-08-11

Release note: 0.3.0 below was merged to main but never tagged, so it never
reached PyPI. This release ships both — PyPI jumps 0.2.1 → 0.4.0.

### Added
- **Eight more sourced failure cases** — `hundred-percent-coverage`,
  `clean-architecture` and `oop-everywhere` move to `filled` (10 of 12 now);
  `tdd` gains two more cases. Same three-gate vetting as the first batch.
  Highlights: Lebrero's IG account and Coplien's coverage-gaming client for
  coverage; Brodwall's fifteen-layer client and Bogard's onion-architecture
  cracks for clean architecture; Neversoft's two-year inheritance unwind and
  Django's CBV critique for OOP-everywhere; Jeffries' Sudoku series — carried
  WITH his 2022 dispute of the moral — and Coplien's switched-off suites for
  TDD. One verifier-mandated correction applied before landing: Coplien's
  Maven anecdote happened at his own job in Denmark, not a consulting audit.
  Remaining drafts: `self-documenting-code` (empty by standard) and
  `scope-creep-feature`.
- **`archdogma explain TARGET`** — the catalog as a mentor. One entry,
  whole: the rule as preached, where it comes from, the conditions under
  which it fails, who paid for it (with sources), the counter-position
  (with attribution), when to follow, when to break, and the one signal
  that it is already breaking. TARGET resolves as dogma id, candidate id,
  number, detector tag (a tag claimed by several entries shows all of
  them), or title fragment; misses exit non-zero with suggestions.
  `--format json` emits the full entry; `--speak` mirrors `probe --speak`.
  Lives in `mentor.py`, registered onto the CLI group — cli.py sits one
  definition under its own god-module threshold, and the honest response
  to that is extraction, not exemption.
- **Nine sourced failure cases across four dogmas** — `solid`,
  `premature-optimization`, `functional-purity` and `kiss` move from
  `need_postmortems` to `filled`. Every source URL was fetched and verified
  against the claims this session (two are bot-blocked to scripts — ACM
  Queue, Medium — and additionally verified via archive captures; the entry
  says so). Highlights: Dan North's shadow-codebases account and Seemann's
  "interfaces are not abstractions" for SOLID; Joe Duffy (PLINQ) and Nelson
  Elhage (Sorbet vs Flow) for premature optimization; Discord's mutable Rust
  NIF, Culture Amp's Elm retirement and Twitter Lite's 200ms keypress for
  functional purity; GFS's single master and Go's generics reversal for KISS.
- Two cases researched and REJECTED are recorded as YAML comments so the next
  researcher does not re-tread them: Therac-25 under KISS (documented motive
  was expense plus faith in software, not a simplicity doctrine) and
  Debian/OpenSSL under self-documenting-code (third-party analysis, no
  no-comments policy in evidence). `self-documenting-code` stays
  `need_postmortems` — an honest empty beats a stretched fit.
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
