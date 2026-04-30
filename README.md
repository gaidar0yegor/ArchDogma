# ArchDogma

<div align="center">
  <img src="docs/assets/archdogma-badge.jpg" alt="ArchDogma badge" width="300">
</div>

> **Let me tell you a story.**

Analyzes one function — honestly, without made-up numbers.
Shows sacred rules of programming — with real post-mortems, not horoscopes.

Two verifiable things. Not one beautiful one.

---

## Why This Exists

90% of the time you're not writing new code. You're trying to understand old code. Comments lie. Function names lie. Documentation was outdated before it was even finished. Running legacy code to understand how it works isn't understanding — it's Russian roulette.

And you keep running into dogmas. "Always write tests", "no copy-paste", "clean code above all", "OOP or you're not serious". Nobody tells you **when** these rules start strangling the system.

ArchDogma takes on both problems.

---

## What It's Made Of

### Function Probe

Analysis of one function. Verifiable.

- What it actually does (not what the comments say)
- What hidden assumptions are baked in
- Where it's most likely to shoot you in the foot
- Trust Score — how much you can rely on it

Ground truth is verified here: AST, types, exceptions, actual execution. No "expert" numbers pulled from thin air.

### Catalog of Dogmas

A catalog of programming's sacred cows — with **real** post-mortems.

Each dogma covers:
- What it says
- Under what conditions it starts to strangle
- Real failure cases with links
- An honest verdict

If there's no link — it's marked `[NEED POSTMORTEMS]`. Making things up is not allowed (see [catalog rules](DOGMAS.md)).

### How They Connect — A Concrete Example

Function Probe finds 7 levels of inheritance in a function → tags it `deep-inheritance`.
The Catalog for that tag returns: "Here are 2 real cases where `deep-inheritance` became a brain tumor: [link], [link]. Typical parameters: team > 10, code age > 3 years."

Not an abstract "try to simplify". But: "here's who already slipped, here's what the fall looked like".

In v0.1 the connection is implemented dumbly and honestly — via pattern-match on AST. No semantic magic. When pattern-match stops working, we'll honestly add something smarter.

---

## What's Actually in v0.1 (Honest Scope)

- **Function Probe** for a single Python function — AST analysis, typical patterns (`deep-inheritance`, `n-layers-deep`, `test-heavy`), Trust Score on verifiable signals (code age, test coverage, complexity)
- **3 fully filled dogmas** in the catalog with real post-mortem links:
  1. **Microservices for everything** (Segment, Prime Video, and friends)
  2. **TDD as law** (DHH, 2014)
  3. **DRY / premature abstractions** (Sandi Metz)
- The remaining 7+ dogmas are in the catalog as drafts (`[NEED POSTMORTEMS]`). We **don't hide** that the catalog is in its early stages. An honest "Draft" label is in the header
- **Voice mode** — "Tell me the story" — from day one, not "later"

Realistic horizon: 2–4 months. Not 3 weeks, not a year.

---

## What It Can't Do (And We Say So Upfront)

- Does not predict when your team will burn out. We're not sociologists or fortune-tellers.
- Does not simulate "physics" of dogmas via JEPA / world models. For now this can't be done honestly — ground truth can't be synthesized.
- Does not analyze an entire repository in one shot. State space explosion is real; many people have already broken their heads on it.

If at some point we start selling these three — beat us with sticks. That's a betrayal of the idea.

---

## Accessibility Is Not a Feature

We won't add it "later". We're building so that a sighted and a blind engineer get the **same** level of code understanding from day one.

If a blind developer can't get the same truth about code as a sighted one — we built garbage.

---

## Our Approach

```
Function  →  File  →  Module  →  Service
```

Each next level appears only after the previous one works honestly.

**We don't trust comments.**
**We don't trust names.**
**We don't even trust ourselves.**
**We verify.**

---

## How to Help

Open source. No money needed. It just needs to work honestly.

- **Blind and low-vision engineers** — you're the primary reviewers of voice mode. Without you, everything else is just pretty arrows
- **People scarred by dogmas** — send a post-mortem. Which dogma was strangling you, under what conditions. That's the fuel for the catalog
- **Realism reviewers** — if you see a number or statement in the catalog without a link, open an issue with the `honesty-bug` label

Issues and PRs — right here.

---

## License

MIT. Fork it, break it, improve it.

If your fork doesn't work by voice or outputs unverified "expert" numbers without links — **don't call it ArchDogma**.

🦫
