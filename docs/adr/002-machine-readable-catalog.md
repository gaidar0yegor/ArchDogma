# ADR-002: Machine-readable catalog — single YAML source, markdown is generated

## Status

Accepted — 2026-04-18.

## Context

After v0.1.0-alpha1 Probe outputs `Catalog links: (none — Probe→Catalog wiring ships with ADR-002)`. This is an honest placeholder, but we can't move forward without it.

Three technical requirements accumulate simultaneously:

1. **Probe → Catalog wiring.** Future Tier 1 detectors must be able to say not just `[deep-nesting]`, but `[deep-nesting] → §3 DRY, §8 Self-documenting`. Grepping over markdown is naive, fragile, slow, and won't survive header renames.
2. **Catalog growth.** In v0.1 — 16 dogmas (3 filled, 13 stubs) + list of candidates. We expect growth to 25–30 within six months. A manual index "name → number → tags" is unmaintainable.
3. **Catalog rule validation.** We already have four rules (every claim with a source, no made-up numbers, etc.). Without a schema, these rules exist only in prose. The machine must check them, otherwise `honesty-bug` becomes recursive.

Three format options were considered (discussion 2026-04-18):

1. YAML frontmatter inside `DOGMAS.md`.
2. Separate `catalog/dogmas.yaml` + hand-written `DOGMAS.md`.
3. Single YAML source, `DOGMAS.md` is generated.

## Decision

Option **(3): single YAML, markdown is a generated artifact.**

- `catalog/dogmas.yaml` — **single source of truth** for the catalog.
- `DOGMAS.md` — generated file. First line: `<!-- AUTO-GENERATED from catalog/dogmas.yaml — DO NOT EDIT BY HAND. Run: archdogma catalog render -->`.
- Edits go into YAML, `DOGMAS.md` is regenerated before commit. A PR that manually edits `DOGMAS.md` fails CI.

### Schema v1

```yaml
schema_version: 1
updated: 2026-04-18

preamble: |
  <static introductory text — framework, rules, format>

postamble: |
  <"How to contribute" section>

dogmas:
  - id: dry                      # slug, stable between versions
    number: 3                    # ordinal number in catalog
    title: "DRY (Don't Repeat Yourself)"
    v01_priority: true           # 🎯 marker in output
    status: filled               # stub | draft | filled

    definition: "Never copy-paste. Any repetition is a candidate for abstraction."
    origin: "«The Pragmatic Programmer», Hunt & Thomas, 1999."

    failure_conditions:
      - "When two similar things are merged into one abstraction and then diverge."
      - "Shared libraries between teams with different release cycles."
      - "Too early abstraction (before 3rd real use case)."

    failure_cases: need_postmortems    # or list {title, source_url, summary}
    success_cases: need_data

    counter_dogmas:
      - name: "WET"
        attribution: "folk, anonymous"
        thesis: "Don't abstract until you've seen the repetition twice."
      - name: "Rule of Three"
        attribution: "Don Roberts via Martin Fowler, «Refactoring» (1999)"
        thesis: "Three repetitions — only then a candidate for abstraction."
      - name: "The Wrong Abstraction"
        attribution: "Sandi Metz, 2016"
        source_url: "https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction"
        thesis: "Duplication is far cheaper than the wrong abstraction."
      - name: "AHA (Avoid Hasty Abstractions)"
        attribution: "Kent C. Dodds, 2019"
        source_url: "https://kentcdodds.com/blog/aha-programming"

    honest_verdict:
      status: draft_awaiting_cases    # draft_awaiting_cases | final | pending
      follow_when:
        - "Knowledge repeats (business rule, formula, invariant), not code form."
        - "You see the third repetition (Rule of Three)…"
      break_when:
        - "Two code pieces look the same but change for different reasons."
        - "The abstraction crosses team or service boundaries."
      main_signal: "Every new requirement adds an if-flag to the 'shared' function."

    related_tags:                  # AST tags that map to this dogma
      - wrong-abstraction          # future Tier 1/5

candidates:
  - title: "God File / God Class"
    note: "Anti-pattern consequence, not a dogma."
    sources:
      - title: "SQLite amalgamation (deliberate performance decision)"
        url: "https://sqlite.org/amalgamation.html"
```

Required fields: `id`, `number`, `title`, `status`, `definition`. Everything else is optional with explicit defaults.

### Rules the validator will check

Rules are a direct port of the catalog rules from `DOGMAS.md` to machine form:

- Every `counter_dogma` must have `attribution`. Without author → `honesty-bug`.
- Any "real" case link must be either a valid URL or a string marker `need_postmortems` / `need_data`.
- `id` is unique in the catalog.
- `number` is unique and continuous in sequence (1, 2, 3, …).
- If `v01_priority: true`, then `status` cannot be `stub` (priority dogmas must be at least `draft`).
- `honest_verdict.status: final` requires non-empty `follow_when`, `break_when`, `main_signal`.

### Tooling

- `archdogma catalog render` — YAML → `DOGMAS.md`.
- `archdogma catalog validate` — schema and rule check (offline; URL validation optional via `--check-urls`).
- CI: `validate` + `render --check` (diff of generated vs committed → fail on mismatch).

### Contributor Contract

1. Edit `catalog/dogmas.yaml`.
2. Before commit: `archdogma catalog render`.
3. Commit both files (`dogmas.yaml` + `DOGMAS.md`) as a pair.
4. CI enforces it anyway — if you forgot step 2, the build is red.

## Consequences

### Positive

- **Single source of truth.** Drift between machine and human view is impossible by design.
- **Catalog rules become executable.** "Every claim with a source" — from ethics to CI check.
- **Probe↔Catalog wiring** is trivial: tag → `related_tags` inverse lookup → list of `Dogma` objects.
- **Structured data for free.** Future IDE plugins, web wrappers, reports get ready YAML without re-parsing markdown.
- **Counter-dogma attribution formalized.** You can't write a `counter_dogma` without `attribution` — the validator rejects it. This matches the existing catalog rule, now machine-enforced.

### Negative

- **YAML is not markdown.** Editing multi-paragraph `honest_verdict` in YAML is less pleasant than in pure markdown. Mitigation: block scalars (`|`), splitting into `follow_when`/`break_when` lists.
- **Barrier for non-technical contributors.** Someone wanting to send a case now hits YAML syntax. Mitigation: issue template + ready YAML snippet in CONTRIBUTING, we transfer it to the file ourselves.
- **New bug surface.** Renderer and validator are code that can break. A renderer bug breaks the `DOGMAS.md` build → breaks all PRs. Mitigation: wide test coverage of renderer + snapshot test.
- **`DOGMAS.md` in git duplicates YAML.** Git history shows both files — reviewing .md diff and .yaml diff simultaneously. Mitigation: in PR template, ask to look at YAML; .md is for visual formatting check.

### Neutral

- Static text (preamble, postamble) lives inside YAML as block scalars. Alternative — separate `dogmas.md.jinja2` template — deferred until real need for templating logic appears. For now `preamble: |` is sufficient.

## Alternatives Considered

### (1) YAML frontmatter in `DOGMAS.md` — rejected

```markdown
---
id: dry
number: 3
counter_dogmas: [...]
---
# 🎯 DRY ...
```

- Hybrid parser (YAML + markdown in one file). Two sources of parser bugs per contribution instead of one.
- Frontmatter still duplicates key fields from main text (name, formulation, cases) → same drift problem, but within one file.
- YAML frontmatter limitation in most tools — one block at the start of file. 16+ dogmas in one document don't fit organically.

### (2) Separate `catalog/dogmas.yaml` + hand-written `DOGMAS.md` — rejected

- **Two sources of truth.** Drift is a matter of when, not if.
- CI check "everything in .md is in .yaml" verifies *presence*, not *content match*. You can sync the index and desync the text — the check won't catch it.
- Doubles cognitive load on contributor: "now edit both".

## Migration Plan

1. Port current `DOGMAS.md` to `catalog/dogmas.yaml` manually (one-shot).
2. Implement `archdogma.catalog.loader.load_catalog()` (Pydantic or dataclass + manual validation — decided at implementation).
3. Implement renderer → `archdogma.catalog.renderer`.
4. Generate `DOGMAS.md` from YAML, compare diff with current version manually, patch YAML until full match.
5. Commit the pair `dogmas.yaml` + `DOGMAS.md` as the first post-ADR-002 pair. Release: **v0.1.0-alpha2**.
6. Enable CI check on subsequent PRs.

Current `src/archdogma/catalog/loader.py` is an explicit stub with `NotImplementedError("see ADR-002 for planned format")`. After migration it's rewritten completely.

## Known Limitations of Schema v1

- **Relationships between dogmas are not modeled.** "§3 DRY conflicts with §7 SOLID at scale" — remains in `honest_verdict` prose. If a real need for a relationship graph appears — schema v2.
- **URL validation offline by default.** Link-rot detection (`--check-urls`) is an option, not enabled in CI by default, so external site unavailability doesn't break our builds.
- **Localization.** Catalog is in English. Fields `definition`, `origin`, etc. are single-language. Translation is not in v0.1 scope.
- **`related_tags`** — list of tag names as strings. Cross-reference with actual `TIER1_DETECTORS` — validator's responsibility, not schema's.

## Expected Next ADRs

- **ADR-003:** Trust Score — specific input signals and weights for Probe output.
- **ADR-004:** Voice mode — TTS backend and output shape for screen readers.
- **ADR-005:** Cross-function / file-level detectors (step up the README ladder "Function → File → Module → Service").
