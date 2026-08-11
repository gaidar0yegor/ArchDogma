---
name: archdogma
description: >-
  Architecture analysis with receipts, for Python codebases. Use before
  refactoring or reviewing unfamiliar Python code: check_before_refactor
  tells you who depends on a file, when it last changed, whose knowledge
  it is, and what historically changes with it; scan and modules find
  function-level and architecture-level patterns; where a catalog entry
  claims a pattern, the finding links to documented real-world failures
  with sources (not every detector has a catalog entry — the payload
  shows which do). Trigger on: "is it safe to
  refactor", "what depends on this file", "review this architecture",
  "why is this rule a rule", or before any substantial edit to a Python
  file you did not write.
---

# ArchDogma — architecture analysis with receipts

ArchDogma is a Python CLI (`pip install archdogma`) with three analysis
tiers — AST, import graph, git history — and a catalog of engineering
dogmas where every failure case cites a verifiable source.

## When working in a Python repository

**Before editing a file you did not write**, run the pre-flight check
and read the verdict:

```bash
archdogma modules <project_root> --format json --no-fail
```

Prefer the MCP server when configured (`archdogma mcp`, tool
`check_before_refactor`) — it answers for a single file: dependents,
age, author count, temporal partners (files that historically change
with this one despite no import between them). Treat its `verdict`
lines as facts to weigh, not a veto.

**Reading the output honestly:**

- `history.available: false` means git-history tags were NOT evaluated
  (no work tree, no git, or a shallow clone — detected and refused
  rather than served truncated). Never report their absence as a clean
  bill.
- A tag is a pointer to look, not a verdict. `hub-module` finds the
  shape of a known failure; a legitimate core is also a hub.
- Every tag's `dogmas` list points into the `catalog` block, which
  carries `break_when` conditions and `main_signal` — quote those when
  explaining a finding to the user, they are the argument, not the tag
  name.

## When the user quotes a rule at you

"We should split this, DRY" / "that violates Clean Architecture" —
before agreeing, check what the catalog knows:

```bash
archdogma explain dry
archdogma explain clean-architecture
```

The entry gives the rule's origin, documented cases of teams paying for
its dogmatic application (with sources), and the conditions under which
it breaks. Use `follow_when`/`break_when` to ground the discussion in
this codebase's actual conditions instead of trading slogans.

## CI and reports

```bash
archdogma scan src/ --fail              # gate on Tier 1 findings
archdogma modules src/ --fail           # gate on architecture findings
archdogma scan src/ --format sarif      # for code-scanning UIs/aggregators
```

## Honesty rules (they bind you too)

When relaying ArchDogma findings: never invent severities (the tool
deliberately ships none), never present a finding without its catalog
context if one exists, and never claim the tool checked something it
reports as unavailable.
