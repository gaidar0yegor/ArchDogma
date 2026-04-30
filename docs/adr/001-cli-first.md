# ADR-001: CLI-first architecture for v0.1

## Status

Accepted — 2026-04-18.

## Context

We need to choose the delivery form for ArchDogma v0.1. Three candidates were considered (see discussion 2026-04-18): Python CLI, Web app, VSCode/IDE extension.

Key selection criteria:
- Accessibility from day one (requirement from the manifest in README).
- Voice mode locally, without network dependency.
- One language (Python already chosen as the AST analysis language).
- Minimum technologies and scope creep in v0.1.
- Minimum time-to-first-probe.

## Decision

ArchDogma v0.1 is implemented as a **Python CLI**.

**Stack:**
- Python `>=3.11` (stdlib `tomllib`, `ast` is modern enough, pattern matching available)
- `click` — CLI framework
- `rich` — optional pretty-output, **disableable** via `--plain` (see below)
- `pyttsx3` — cross-platform TTS; with fallback to subprocess of native `say` (macOS) / `espeak-ng` (Linux) / SAPI (Windows)
- `gitpython` — optional, for Tier 3 tags (`old-code`, `high-churn`)
- `pytest` + `ruff` + `mypy` — dev

**Build backend:** `hatchling`. **Layout:** `src/archdogma`.

**Output default inversion (a matter of principle):**
The typical CLI approach is rich formatting by default, `--plain` as fallback. We do the **opposite**: plain structured text by default (parseable by screen readers), rich formatting via `--pretty`. This is a direct consequence of the "accessibility is not a feature" manifesto.

## Consequences

### Positive

- Screen readers work in the terminal out of the box on Linux/macOS.
- Voice via local TTS without network dependency.
- One language — one CI, one test runner, one dependency ecosystem.
- `pip install -e .` → `archdogma probe <file>` — a working command from the first commit.
- CLI integrates into pre-commit hooks, CI pipelines, IDE tasks without extra wrappers.
- Lowest time-to-first-probe of the three options.
- Web UI on top of CLI core remains possible for v0.2+ without rewriting.

### Negative

- Windows TTS quality from `pyttsx3` is weaker than native macOS `say` / Linux `espeak-ng`. Documented as known limitation.
- No graphical AST visualization. Tags are output as text (file + line + column + description). Tree visualization in CLI is possible, but not IDE-level.
- Not embedded in the editor — user switches context between IDE and terminal.
- For non-developer users, CLI is a barrier. In v0.1 this is **explicitly out of scope**: ArchDogma v0.1 is a tool for engineers.

### Neutral

- IDE extension is possible in v0.2+ via subprocess to CLI (compromise, but a working pattern — this is how `ruff`, `mypy`, `pytest` integrations work).
- Web UI is possible in v0.2+ as a thin FastAPI wrapper over the CLI core.

## Alternatives Considered

### Web app — rejected for v0.1

- AST analysis requires either a separate Python backend (dual stack) or tree-sitter WASM in the browser (added complexity).
- Screen reader compatibility on web is manual work under WCAG 2.1 AA, not a freebie.
- Hosting / deploy / HTTPS / logs — ops that shouldn't exist in v0.1.
- Time-to-v0.1 extends by at least 3–4 weeks.

### VSCode/IDE extension — rejected for v0.1

- TypeScript/JS stack alongside Python = two languages, two CIs, two test runners.
- Market covered only by VSCode — JetBrains/Neovim users left behind.
- Voice in IDE requires a desktop-hack or external TTS bridge.
- Extension review process adds release time.
- Time-to-v0.1 extends by at least 3–4 weeks.

Both options remain open for v0.2+. The CLI core is designed so it can be called as a subprocess from web or extension.

## Known Limitations of v0.1, Explicitly Accepted

- **Windows TTS quality** — lower than on macOS/Linux. Documented.
- **No graphical AST visualization.** Output is text.
- **No machine-readable catalog format.** `DOGMAS.md` for now is human-readable only. For Probe → Dogma linkage, either YAML frontmatter per dogma or a separate `catalog/index.yaml` is needed. That's the next ADR.
- **Tier 5 tags (semantics) not implemented** — see `AST_TAGS_DRAFT.md`.

## Expected Next ADRs

- **ADR-002:** Machine-readable format for the dogma catalog (frontmatter vs separate index).
- **ADR-003:** Trust Score formula — specific input signals and weights.
- **ADR-004:** Voice mode — exact TTS backend and output shape for screen readers.
