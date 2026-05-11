# ArchDogma

<div align="center">
  <img src="docs/assets/archdogma-badge.jpg" alt="ArchDogma badge" width="300">
</div>

> **A catalog of real engineering failures. The scanner is just a way to find them in your code.**

---

## The Catalog

Programming has sacred rules. "Always test." "Use microservices." "No copy-paste." "Clean Architecture." Nobody tells you **when these rules start strangling your system**.

ArchDogma collects real postmortems — companies that followed a rule and paid for it. Not to say the rules are wrong. To say they have conditions.

**Current catalog:** 12 dogmas, 11 with postmortems.

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
```

### Selected postmortems

**Microservices for everything → Segment (2022)**
140+ services, one per data destination. Routing logic duplicated 140 times. On-call couldn't hold the system in their head. Rewrote as one Go service. Delivery reliability improved.
→ [full case](DOGMAS.md#4-microservices-for-everything-)

**DRY → shared config with 14 flags (QuackNet, 2025)**
ProbeConfig abstracted after 2 similar structs. Grew to 14 flags as 4 subsystems diverged. A Kafka change broke the Wi-Fi probe. Split back into 3 structs. The abstraction cost more than the duplication would have.
→ [full case](DOGMAS.md#3-dry-dont-repeat-yourself-)

**TDD → over-mocked suite that passed but missed integration bugs (Basecamp, 2014)**
Tests mocked every boundary for unit purity. Integration bugs multiplied. DHH: "Test-driven development as ideology led to designing for tests instead of designing for the problem."
→ [full case](DOGMAS.md#6-tdd-test-driven-development-)

**OOP inheritance → 7 files for a 5-line business rule (Java EJB era, 2002)**
EJB 2.x required Home + Local + Remote interfaces + XML for every entity. Rod Johnson documented it and built Spring to eliminate the inheritance tax.
→ [full case](DOGMAS.md#5-oop-as-the-only-truth-inheritance-everywhere-)

---

## The Scanner

Once you know which dogmas are in play, find them in your code:

```bash
# Probe one function — Trust Score, AST tags, linked dogmas
archdogma probe mymodule.py -f MyClass.process

# Scan a project — CI-ready
archdogma scan src/
archdogma scan src/ --fail   # exit 1 if any tag fires
archdogma scan src/ --format json
```

The scanner detects 12 Tier 1 patterns — `deep-inheritance`, `god-class`, `magic-numbers`, `if-on-parameter`, `dynamic-magic`, `broad-except`, `mutable-default-arg`, `too-many-returns`, and more. Each tag links back to the catalog.

**The scanner is secondary.** The catalog is the point. If the catalog didn't have real postmortems, the scanner would just be another linter. The postmortems are what make a detected pattern meaningful: "here's who followed this rule and where it broke them."

---

## Install

```bash
pip install archdogma
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
