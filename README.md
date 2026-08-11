# ArchDogma

<div align="center">
  <img src="docs/assets/archdogma-badge.jpg" alt="ArchDogma badge" width="300">
</div>

> **A catalog of real engineering failures. The scanner is just a way to find them in your code.**

Linters see code. ArchDogma sees **history × structure** — and every finding
comes with a receipt: a documented, sourced case of a real team paying for
this exact pattern.

### Where this sits

Claims below are checkable; sources linked. Corrections welcome via the
`honesty-bug` label.

| Tool | Import-graph contracts | Git history × structure | Findings linked to sourced real-world failures | Free for private code |
|---|---|---|---|---|
| [import-linter](https://github.com/seddonym/import-linter) | yes | no | no | yes |
| [tach](https://github.com/gauge-sh/tach) | yes | no | no | yes |
| [pydeps](https://github.com/thebjorn/pydeps) | visualisation only | no | no | yes |
| [CodeScene](https://codescene.com/pricing) | partial | **yes** | no | no (OSS only; CLI needs a token) |
| [repowise](https://github.com/repowise-dev/repowise) | no | **yes** | aggregate statistics, not per-finding sources | yes (AGPL) |
| **ArchDogma** | **yes — history-priced** | **yes** | **yes — external cases fetch-verified; first-party cases labelled as such** | yes (MIT) |

---

## The Catalog

Programming has sacred rules. "Always test." "Use microservices." "No copy-paste." "Clean Architecture." Nobody tells you **when these rules start strangling your system**.

ArchDogma collects real postmortems — companies that followed a rule and paid for it. Not to say the rules are wrong. To say they have conditions.

**Current catalog:** 12 dogmas — 11 filled with sourced failure cases — and 22 candidates, the Tier 2/3 ones now carrying incident cases of their own (Knight Capital, Cloudflare 2025, Reddit Pi-Day, event-stream, core-js).

Browse the full catalog: [DOGMAS.md](DOGMAS.md)

Or from the CLI:

```bash
pip install archdogma

# View all dogmas with their status and linked cases
archdogma dogmas

# Search for a specific pattern
archdogma search "microservices"
archdogma search "inheritance"
archdogma search "coverage"

# Get the whole argument for one entry — rule, origin, cases, when to break it
archdogma explain dry
archdogma explain circular-import   # by detector tag
archdogma explain 4                 # by number
archdogma explain dry --speak       # spoken summary, same as probe --speak
```

### Selected postmortems

**Microservices for everything → Segment (2018)**
140+ services, one per data destination. Routing logic duplicated 140 times. On-call couldn't hold the system in their head. Folded back into one monolithic destination service. Delivery reliability improved.
→ [full case](DOGMAS.md#4-microservices-for-everything-)

**DRY → the wrong abstraction (Sandi Metz, 2016)**
A shared function serving 2 callers grows flag parameters as callers diverge, until every change breaks someone. Metz's rule: prefer duplication over the wrong abstraction. (The catalog also carries a first-party case of ours — QuackNet's 14-flag ProbeConfig — labelled first-party, because our rules require the label where there is no external link.)
→ [full case](DOGMAS.md#3-dry-dont-repeat-yourself-)

**TDD → "a dense jungle of service objects, command patterns, and worse" (DHH, 2014)**
Verbatim: "Test-first units leads to an overly complex web of intermediary objects and indirection in order to avoid doing anything that's 'slow'." A first-person renunciation by the named engineer — an essay, not an incident report, and the catalog labels it as exactly that.
→ [full case](DOGMAS.md#6-tdd-test-driven-development-)

**OOP inheritance → two years to unwind the Tony Hawk object hierarchy (Neversoft, 2007)**
The industry-standard deep game-object hierarchy became a blob across three shipped titles; Mick West's first-person account of refactoring it to components while shipping a game a year.
→ [full case](DOGMAS.md#5-oop-as-the-only-truth-inheritance-everywhere-)

---

## The Scanner

Once you know which dogmas are in play, find them in your code:

```bash
# Probe one function — Trust Score, AST tags, linked dogmas
archdogma probe mymodule.py -f MyClass.process

# Scan functions and classes — CI-ready
archdogma scan src/
archdogma scan src/ --fail   # exit 1 if any tag fires

# Analyse module structure and change history
archdogma modules src/
archdogma modules src/ --all --no-history
```

**The scanner is secondary.** The catalog is the point. If the catalog didn't have real postmortems, the scanner would just be another linter. The postmortems are what make a detected pattern meaningful: "here's who followed this rule and where it broke them."

### Three tiers, three kinds of question

**Tier 1 — one function or class.** `deep-nesting`, `long-function`, `god-function`, `too-many-params`, `if-on-parameter`, `magic-numbers`, `dynamic-magic`, `broad-except`, `mutable-default-arg`, `too-many-returns`, `god-class`, `deep-inheritance`.

**Tier 2 — the import graph.** `circular-import`, `hub-module`, `god-module`, `unstable-dependency`. Questions that do not exist inside a single file: what does everything depend on, and do the dependencies point where the folder names claim they do.

**Tier 3 — structure crossed with `git log`.** `load-bearing-wall`, `churn-hotspot`, `single-author-hub`, `temporal-coupling`. Tier 2 knows that forty modules import `core.py`; Tier 3 knows nobody has changed it in three years. Neither fact is alarming alone. And `temporal-coupling` finds the pairs that keep changing together while neither imports the other — the relationship no graph can show you.

Tier 3 needs a git work tree. Outside one — a shallow clone, a tarball, no git — every Tier 3 detector goes silent and says so. A missing history is not evidence of a young file.

### For agents and CI

`--format json` is the machine-readable surface, and it carries the catalog with it:

```bash
archdogma modules src/ --format json
```

Every tag reports the ids of the catalog entries that claim it. Those entries are emitted once at the top level with `break_when`, `main_signal`, and links to the postmortems:

```json
{
  "tags": [{"name": "circular-import", "dogmas": ["clean-architecture"]}],
  "catalog": {
    "entries": {
      "clean-architecture": {
        "break_when": ["Team smaller than 5 and single product — ..."],
        "main_signal": "You spend more time writing mappers between layers ..."
      }
    }
  }
}
```

That is the difference between a linter and this: `god-module at line 1` is no more useful than `C0301 line too long`. A tag with the conditions under which its dogma stops working is something you can argue with.

### Contracts — priced by history

Declare architecture rules in `pyproject.toml`; every violation carries the importing file's git history, because a layering breach in this quarter's churn-hotspot and one in a file untouched since 2023 are the same boolean and very different work items:

```toml
[[tool.archdogma.contracts]]
name = "core must not import web"
type = "forbidden"          # forbidden | layers | independence
source = ["app.core"]
forbidden = ["app.web"]
```

```bash
archdogma contracts .                      # fail on any violation
archdogma contracts . --fail-only-active   # report all, gate only violations
                                           # in files changed in the last 90d
```

Contract semantics follow import-linter's (credit where due — it's the standard). What it can't do and this can: `--fail-only-active` still *reports* dormant violations — it gates the exit code, it never hides findings. And without usable git history every violation counts as active: unknown is not dormant.

Our own contracts are declared in this repo's `pyproject.toml` and checked in CI.

### MCP server

```bash
pip install 'archdogma[mcp]'
archdogma mcp                # stdio server for Claude Code, Cursor, any MCP client
```

Five tools, all local, no tokens, MIT: `scan_functions`, `analyze_modules`, `explain_dogma`, `list_dogmas`, and the one the others exist to support — `check_before_refactor`: an agent about to edit an unfamiliar file asks "what am I about to break?" and gets the answer from the import graph and the git history: who depends on it, when it last changed, whose knowledge it is, and what historically changes with it.

Claude Code config (`.mcp.json`):

```json
{"mcpServers": {"archdogma": {"command": "archdogma", "args": ["mcp"]}}}
```

A Claude Code skill ships in [integrations/claude-code/](integrations/claude-code/) — copy it into `.claude/skills/` to teach the agent when to reach for these tools.

### SARIF

```bash
archdogma scan src/ --format sarif
archdogma modules src/ --format sarif
```

SARIF 2.1.0 for code-scanning UIs and review platforms. Every result is level `warning`, deliberately: this tool ships signals with context, not severities, and inventing a severity scale would claim a precision the detectors do not have.

---

## Install

```bash
pip install archdogma
```

Core pulls exactly two dependencies (`click`, `pyyaml`) — the analyzers
themselves are pure stdlib. Optional extras:

```bash
pip install 'archdogma[pretty]'   # rich rendering for --pretty
pip install 'archdogma[voice]'    # pyttsx3 TTS fallback — only needed on
                                  # Windows; macOS (say) and Linux
                                  # (espeak-ng) speak with no extra at all
```

Or from source:

```bash
git clone https://github.com/gaidar0yegor/ArchDogma
cd ArchDogma
pip install -e .
```

---

## Why This Exists

90% of engineering is understanding old code. And that code is full of dogmas applied without context. "Always test" — gamified into 100% coverage with no assertions. "Microservices" — applied to a 3-person team building one product. "Clean Architecture" — 5 layers for a CRUD app.

The pattern is predictable: a good rule gets applied without its conditions. Nobody wrote down when it stops working. The postmortems exist to fix that.

---

## Honesty rules

- Every postmortem has a source link, or is explicitly marked first-party / `source_url: null`.
- Built with heavy AI assistance — the commit trailers say so on purpose. Sources are re-verified by a human before releases, and `tools/verify_sources.py` re-checks every link so you don't have to trust either of us.
- Every claim can be challenged via the `honesty-bug` label on GitHub.
- The scanner produces verifiable AST signals. No "expert" numbers without evidence.
- If a detector doesn't exist yet, the catalog says so: `[NEED POSTMORTEMS]`.

---

## Accessibility

Voice mode from day one:

```bash
archdogma probe mymodule.py -f my_function --speak
```

Sighted and blind engineers get the same information. Not "later" — from the start.

---

## Contributing

**What we need most:** real postmortems. Which dogma was applied at your company, under what conditions, and what broke.

- **Post-mortem sources** — open an issue with `postmortem` label
- **Blind/low-vision engineers** — primary reviewers of voice mode
- **Honesty bugs** — if you see a claim without a source, open `honesty-bug`

Source of truth for the catalog: `catalog/dogmas.yaml`. `DOGMAS.md` is auto-generated via `archdogma render-catalog`.

---

## License

MIT. Fork it, improve it.

If your fork drops the honesty rules or voice mode — don't call it ArchDogma.

🦫
