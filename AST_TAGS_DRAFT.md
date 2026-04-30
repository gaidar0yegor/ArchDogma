# AST Tags — v0.1 Draft

> ⚠️ **Status: DRAFT.** Draft vocabulary of tags that Function Probe can assign via AST analysis. Every threshold either has a source or is explicitly marked `[default, configurable, heuristic]`. Without this we become the very dogma we're warning against.

## Rules (from DOGMAS.md, applied recursively to ourselves)

1. **Threshold without source = mark `[default]`.** We don't write "function breaks at 200 lines" as fact.
2. **Semantics is acknowledged as semantics.** If a tag requires understanding code intent — we honestly say "not v0.1, hallucination without ground truth".
3. **Segregation by detection method.** AST-tag, git-tag, and coverage-tag are three different mechanisms, not one thing.
4. **v0.1 — minimal set.** Better 4 honest tags than 25 half-working ones.

---

## Detection Tiers

| Tier | What's Required | Example |
|---|---|---|
| **1** | Pure AST of one file | `deep-nesting`, `long-function` |
| **2** | AST + cross-file usage graph | `premature-abstraction`, `heavy-di` |
| **3** | Git history | `old-code`, `high-churn` |
| **4** | External coverage report | `no-tests`, `low-coverage` |
| **5** | Semantics / intent (NLP) | `wrong-abstraction` (broad), `ritual-tests`, `self-documenting-fail` |

**v0.1 target:** Tier 1 in full, Tier 3 as bonus. Tier 2 and 4 — post-v0.1. Tier 5 — **not doing it**, otherwise hallucination.

---

## Tier 1 — Pure AST Single-File (v0.1 targets)

### `deep-nesting`
Maximum nesting depth of control flow (`if`/`for`/`while`/`try`/`with`) in a function.
- **Threshold:** `≥ 4` `[default, configurable]`
- **Source:** Cognitive Complexity (Sonarsource, 2017) uses nesting as a weighted factor. No single research-backed absolute threshold exists.
- **Dogma links:** §2 Clean Architecture (indirect), §8 Self-documenting code.

### `long-function`
LOC of function without blank lines and comments.
- **Threshold:** `≥ 80` `[default, configurable, heuristic]`
- **Source:** None. Numbers 50/80/100 float around style guides without research backing.
- **Dogma links:** §8 Self-documenting code.

### `god-function`
Extreme length OR branching.
- **Threshold:** `≥ 200 LOC` OR `≥ 15 branch points` `[default, configurable, heuristic]`
- **Source:** None. McCabe 1976 gives cyclomatic complexity `≥ 10` as a signal — this is the closest research-backed reference, and should be considered *instead of* or *alongside* our threshold.
- **Dogma links:** §8 Self-documenting, §2 Clean Architecture.

### `god-class`
Class of excessive size.
- **Threshold:** `≥ 500 LOC` OR `≥ 25 public methods` `[default, configurable, heuristic]`
- **Source:** No universal threshold. Chidamber-Kemerer metrics (1994) give WMC and RFC, but without absolute thresholds.
- **Dogma links:** §5 OOP (God Class), §2 Clean Architecture.

### `deep-inheritance` (single-file layer)
Depth of a class's inheritance chain, visible within one file.
- **Threshold:** `≥ 4` `[heuristic]`
- **Source:** DIT (Depth of Inheritance Tree) — Chidamber & Kemerer, 1994. Basili/Briand/Melo (1996) showed correlation between DIT and defects, but without a single threshold. In practice 5-6 is cited as "definitely painful".
- **v0.1 limitation:** if the base class is in another file — not caught. Full chain is Tier 2.
- **Dogma links:** §5 OOP.

### `if-on-parameter` (narrow version of wrong-abstraction)
Function contains `≥ N` if/elif branches comparing the same parameter to literals. Classic "flag controls behavior".
- **Threshold:** `≥ 3` branches on the same parameter `[default, configurable]`
- **Source:** No formal one, but this is a direct operational expression of Sandi Metz's thesis "The Wrong Abstraction" (2016).
- **Important:** this is the **narrow, honest** version of the tag. Broad "wrong-abstraction" as "code joins different behaviors" — Tier 5, not doing it.
- **Dogma links:** §3 DRY (main signal of abstraction miss).

### `magic-numbers`
Numeric literals in code not assigned to a named constant. Excluding `0`, `1`, `-1`.
- **Threshold:** `≥ 5` per function `[default, configurable, heuristic]`
- **Source:** None.
- **Dogma links:** §8 Self-documenting code.

### `dynamic-magic` (Python-specific)
Use of `getattr`/`setattr`/`delattr`/`eval`/`exec`/`__import__` in a function.
- **Threshold:** any occurrence (binary tag).
- **Source:** Python docs themselves recommend caution; not research, but consensus.
- **Dogma links:** §8 Self-documenting code, §5 OOP (runtime rewriting).

---

## Tier 3 — Git-Based (v0.1 bonus, if time allows)

### `old-code`
File was last changed more than `N` years ago.
- **Threshold:** `> 3 years` `[default, configurable]`
- **Detection:** `git log -1 --format=%ad -- <file>`.
- **Dogma links:** not direct; used as a Trust Score multiplier.

### `high-churn`
File changed `≥ N` times in the last `M` months.
- **Threshold:** `≥ 15 commits in 6 months` `[default, configurable, heuristic]`
- **Source:** Adam Tornhill, "Your Code as a Crime Scene" (2015) — hotspots via churn + complexity. The idea is established; specific thresholds are not.
- **Dogma links:** not direct; signal "constantly being patched here", lowers Trust Score.

---

## Tier 2 — Cross-File (post-v0.1)

Require building a usage graph across the project. In v0.1 **not doing it** — state space and performance.

- `premature-abstraction` — class/function called from ≤ 2 places.
- `heavy-di` — class with `≥ 6` dependencies via constructor.
- `deep-inheritance` (full chain across files).

---

## Tier 4 — Coverage Data (post-v0.1)

Require an external artifact — `.coverage`, pytest report, or manifest. In v0.1 **not doing it** — no guarantee the user has one.

- `no-tests` — function has no associated test (by naming heuristic or import).
- `low-coverage` — function coverage `< 30%`.
- `test-heavy` — file is `≥ 70%` test code relative to production.

---

## Tier 5 — Semantics (NOT doing in v0.1)

Require understanding code intent. Without ground truth = hallucination. Explicit ban in v0.1.

- ❌ `wrong-abstraction` (broad version) — "abstraction joins different behaviors".
- ❌ `ritual-tests` — "test exists but checks nothing".
- ❌ `self-documenting-fail` — "name doesn't explain intent".
- ❌ `monkey-patching` — partially AST-detectable, but "bad" vs "necessary" is semantics.

If reliable ground truth ever appears (verifiable signal, not LLM opinion) — we'll come back. For now — ignored.

---

## Tag-to-Dogma Mapping for v0.1 Priority Dogmas

| Dogma | Related Tier 1 Tags | Linkage Honesty |
|---|---|---|
| **§3 DRY** | `if-on-parameter` | ✅ direct link |
| **§6 TDD** | *(requires Tier 4 — coverage)* | ⚠️ no direct Tier 1 signal |
| **§4 Microservices** | *(not applicable at function level)* | ❌ honest gap |

### Honest Gap #1: §6 TDD
At function level without a coverage report we can't say "this function is untested". A naming heuristic is possible ("function `foo` → look for `test_foo` in `tests/` or `_test.py`"), but that's Tier 4-light. In v0.1 either accept this compromise, or honestly say: §6 TDD linkage works only when the user passes a coverage report.

### Honest Gap #2: §4 Microservices
Function Probe works at function level. Microservices is about organizational design and service boundaries. There's no link at function level and there won't be. Honest: dogma §4 in v0.1 is surfaced by the catalog as a reference, but not triggered by Probe. Waiting for the **Module/Service** level from the README ladder.

---

## v0.1 Minimal Target Set (Specific)

**Implementing 6 tags:**
1. `deep-nesting`
2. `long-function`
3. `god-function`
4. `god-class`
5. `deep-inheritance` (single-file)
6. `if-on-parameter`

**If time allows — 2 more:**
7. `magic-numbers`
8. `dynamic-magic`

**Tier 3 — if time remains:**
9. `old-code`
10. `high-churn`

That's it. No Tier 2/4/5 in v0.1.

---

## What We're NOT Doing in v0.1 (Openly)

- No semantics (Tier 5).
- No usage graph (Tier 2).
- No coverage integration (Tier 4).
- No "teams typically break at X" — any threshold either has a source or is marked `[default]`.
- No tags we can't explain in one line of code.

---

## Next Step After This Draft

Choose the delivery form (CLI / web / VSCode ext). Without it any YAML/JSON tag serialization is work with no destination. Stack discussion — next round.
