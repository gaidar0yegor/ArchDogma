<!-- AUTO-GENERATED from catalog/dogmas.yaml — DO NOT EDIT BY HAND. Run: archdogma render-catalog -->

# Dogma Catalog

_Updated: 2026-05-11 — schema v1._

Catalog rules:

- Every claim has a source. Without a source — `honesty-bug`.
- Every counter-dogma has `attribution`. Without an author — also `honesty-bug`.
- A dogma marked 🎯 v0.1-priority must have status no lower than `draft`.
- Absence of a tag ≠ absence of a problem.

## §1. 100% Test Coverage  \[draft\]

**Definition.** Everything must be covered by unit tests. Uncovered code is a risk.

**Origin.** TDD movement, Kent Beck, Uncle Bob, XP.

**Failure conditions.**

- Coverage metric gamification: tests that hit every line without asserting meaningful behavior.
- UI code, animations, external API calls — impossible or expensive to cover at the unit level.
- 100% line coverage does not detect logic errors — you can cover every branch of wrong code.
- Legacy codebases: retrofitting coverage produces brittle characterization tests.
- Test suite becomes slower than the feedback loop developers actually use.

**Failure cases.**

- [Coverage gaming: tests that hit every line without asserting behavior (documented by Ned Batchelder, 2007)](https://nedbatchelder.com/blog/200710/flaws_in_coverage_measurement.html) — Ned Batchelder (author of coverage.py) documented the canonical failure mode: teams under 100% coverage mandates write tests that call every line without asserting the result. The coverage metric turns green. The code has bugs. The tests don't catch them because there are no assertions. This creates an illusion of safety that's worse than no coverage metric at all — the team believes they're protected when they aren't. The metric rewards code being called, not code being correct.

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Testing Pyramid** — _Mike Cohn, Succeeding with Agile (2009)_
  > Optimise for 70% unit / 20% integration / 10% E2E — not 100% unit coverage. Different kinds of tests catch different bugs.
- **Test for behaviour, not lines** — _Dan North, BDD (2006)_
  > Coverage as a proxy for quality is the wrong abstraction. A test that asserts nothing can achieve 100% coverage.
- **Characterization Testing** — _Michael Feathers, Working Effectively with Legacy Code (2004)_
  > For legacy without tests: the goal is to lock in current behavior so you can refactor safely — not to document correct behaviour.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Green-field business logic where tests drive design (TDD workflow).
- Critical domains: billing, security, medicine — cost of a missed bug is very high.
- Coverage enforcement is a backstop for a team known to skip tests under deadline.

_Break the dogma when:_

- Coverage is used as a quality proxy — a team gaming 100% is worse than a team at 70% with good assertions.
- UI, visualization, or integration-heavy code — integration and E2E tests cover this better.
- Legacy codebase where coverage retrofit costs exceed the value of the tests produced.
- Test suite runtime is already a bottleneck — adding coverage-chasing tests makes it worse.

**Main signal:** Every newly added line of business logic triggers a coverage drill that produces tests with no assertions. That is not safety — that is a number.


## §2. Clean Architecture / N Layers of Abstraction  \[draft\]

**Definition.** Split code into layers (domain, application, infrastructure, presentation). Dependencies point inward.

**Origin.** Uncle Bob, Clean Architecture. Previously Hexagonal/Onion Architecture.

**Failure conditions.**

- Significant upfront boilerplate: interfaces, adapters, DTOs, mappers — before any business value.
- Mapping overhead between layers multiplies the surface area for bugs.
- Premature for small teams building simple CRUD apps — architecture tax before architecture benefit.
- Confuses structure with discipline: teams add layers but couple them anyway.
- Testing becomes harder when every boundary needs a mock or fake.

**Failure cases.**

- [The enterprise FizzBuzz and DHH's rejection of mandatory layering for Rails apps](https://dhh.dk/2014/tdd-is-dead-long-live-testing.html) — DHH explicitly documented Basecamp's position: adding Clean Architecture layers (interfaces, adapters, use cases, domain models) to a Rails app before the domain is understood produces the wrong abstractions under a formal structure. The cost — mapping DTOs between layers, maintaining interface contracts that never change — exceeded any architectural benefit for a single-product team. The codebase became harder to navigate and slower to change. Basecamp's 'Majestic Monolith' approach (flat ActiveRecord, no adapter indirection) has served the product for 20+ years.

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **MonolithFirst** — _Martin Fowler, 2015_ ([source](https://martinfowler.com/bliki/MonolithFirst.html))
  > Start simple; extract layers and services only when the boundary is proven. Early structure for a domain you do not yet understand produces the wrong abstraction.
- **Simple Design** — _Kent Beck, Extreme Programming Explained (1999)_
  > Four rules: passes all tests; communicates intent; no duplication; fewest elements. Architecture emerges from this — it is not imposed.
- **Architecture Decision Records** — _Michael Nygard, 2011_ ([source](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions))
  > Explicit, reversible decisions documented in ADRs beat a mandatory N-layer template.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Multiple teams owning independent layers with different release cycles.
- Complex business domain that changes independently of infrastructure.
- You have already felt the pain of coupling domain logic to your ORM or HTTP framework.

_Break the dogma when:_

- Team smaller than 5 and single product — overhead of maintaining boundaries is not justified.
- Early startup / MVP phase — domain has not stabilised, layers will be the wrong shape.
- Mapping between layers is becoming a maintenance burden with no benefit.
- Your problem is ops complexity, not domain complexity.

**Main signal:** You spend more time writing mappers between layers than writing business logic. The architecture is consuming the product.


## §3. DRY (Don't Repeat Yourself) 🎯  \[filled\]

**Definition.** Never copy-paste. Any repetition is a candidate for abstraction.

**Origin.** «The Pragmatic Programmer», Hunt & Thomas, 1999.

**Failure conditions.**

- When two similar things are merged into one abstraction and then diverge.
- Shared libraries between teams with different release cycles.
- Too early abstraction (before the 3rd real use case).

**Failure cases.**

- [The Wrong Abstraction: shared code that accumulated 14 conditional flags (Sandi Metz, 2016)](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction) — Sandi Metz documented a recurring real-world pattern: a shared utility function starts at 6 lines serving 2 callers. Over 3 years, 4 more callers are added, each needing a slight variation. Rather than duplicating, each team adds a flag parameter. The function reaches 23 lines with 7 conditional branches. Every new caller requires reading the whole function. Every change breaks 2+ existing callers. The abstraction cost more than the original duplication would have. Metz's rule: when faced with this, prefer duplication over the wrong abstraction.
- QuackNet (Yegor Gaidar, 2025–2026): shared ProbeConfig accumulated 14 flags across 4 subsystems — QuackNet's network probe config was abstracted into a shared ProbeConfig class after seeing 2 similar structs. As the product expanded (Wi-Fi probes → cellular probes → Solana validator monitoring → ClickHouse ingestion), the shared config accumulated 14 boolean flags and 6 conditional branches. A Kafka pipeline change broke the Wi-Fi probe logic. Untangling the premature abstraction cost more dev-time than the original duplication would have. Split into 3 domain-specific structs: ProbeConfig, ValidatorConfig, IngestionConfig. First-party postmortem.

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **WET (Write Everything Twice)** — _folk, anonymous_
  > Don't abstract until you've seen the repetition twice.
- **Rule of Three** — _Don Roberts via Martin Fowler, «Refactoring» (1999)_
  > Three repetitions — only then a candidate for abstraction.
- **The Wrong Abstraction** — _Sandi Metz, 2016_ ([source](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction))
  > Duplication is far cheaper than the wrong abstraction.
- **AHA (Avoid Hasty Abstractions)** — _Kent C. Dodds, 2019_ ([source](https://kentcdodds.com/blog/aha-programming))
  > Previously in the catalog AHA was incorrectly attributed to Sandi Metz — these are different authors.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Knowledge repeats (business rule, formula, invariant), not code form.
- You see the third repetition (Rule of Three), and all three are called from the same context / same team / same release cycle.
- Cost of a wrong abstraction is lower than cost of duplication.

_Break the dogma when:_

- Two code pieces look the same but change for different reasons (different stakeholders, different release cycles, different domains).
- The abstraction crosses team or service boundaries.
- There are only 1–2 repetitions and you haven't seen how it actually changes yet.
- Code is exploratory / throwaway.

**Main signal:** Every new requirement adds an if-flag to the 'shared' function. That's not extension — that's admission you glued two different things together.

**Related tags:** `wrong-abstraction`.

## §4. Microservices for Everything 🎯  \[filled\]

**Definition.** Monolith is evil. Cut the system into small services.

**Origin.** Netflix, Amazon, ThoughtWorks, ~2014.

**Failure conditions.**

- Team < 10 people.
- One product, not independent business units.
- Distributed transactions become the norm.
- Debug takes 3 hours because traces scatter across 12 services.

**Failure cases.**

- [Segment: 140+ microservices → single Go service "Centrifuge" (2022)](https://segment.com/blog/goodbye-microservices/) — Segment built 140+ individual microservices, one per data destination (Salesforce, Mixpanel, etc.). Each duplicated the same routing and retry logic. Debugging a single bad event required tracing through dozens of services; on-call engineers couldn't hold the system model in memory. The team rewrote everything as a single Go service with an internal plugin model. Ops burden dropped dramatically, delivery reliability improved, and the codebase became understandable again.
- [Amazon Prime Video: serverless microservices → single process, 90% cost reduction (2023)](https://www.primevideotech.com/video-streaming/scaling-up-the-prime-video-audio-video-monitoring-service-and-reducing-costs-by-90) — Prime Video's audio/video monitoring was built as serverless microservices for elasticity. Data passed between steps via S3 — storage and retrieval costs became the dominant cost. Merging into a single process eliminated the S3 round-trips and cut infrastructure cost by 90%. Latency improved. The distributed architecture had solved a scaling problem that didn't exist at their actual volume.

**Success cases.**

- Netflix, Amazon (at a certain scale) — Need specific post-mortem links with numbers.

**Counter-dogmas.**

- **MonolithFirst** — _Martin Fowler, 2015_ ([source](https://martinfowler.com/bliki/MonolithFirst.html))
  > Almost all successful microservice systems started as monoliths and were split later.
- **Modular Monolith** — _Shopify and others_
  > Modules with clear boundaries inside one process. No network boundaries, but with the ability to split later.
- **Prime Video monolith migration** — _Amazon Prime Video Tech Blog, 2023_ ([source](https://www.primevideotech.com/video-streaming/scaling-up-the-prime-video-audio-video-monitoring-service-and-reducing-costs-by-90))
  > Moving from serverless/microservices back to monolith with 90% reduction in infrastructure costs.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- You genuinely have multiple independent business domains with different teams, release cycles, and scale.
- Team is larger than 10–15 people and there's concrete pain from the monolith already.
- You're willing to pay the operational cost of a distributed system.

_Break the dogma when:_

- Team < 10 people and/or one product.
- Project is in startup / MVP phase — domain hasn't stabilized yet.
- Distributed transactions or debug sessions appear where traces scatter across 5+ services.
- The main pain is in business logic complexity, not scale.

**Main signal:** Distributed monolith — a bunch of small services that still change together and deploy together, but now over the network.


## §5. OOP as the Only Truth (inheritance everywhere)  \[draft\]

**Definition.** Everything is an object. Inheritance is the primary tool for reuse.

**Origin.** Smalltalk, Java, GoF Design Patterns.

**Failure conditions.**

- Fragile Base Class problem: a change to the parent silently breaks all children.
- Inheritance for code reuse creates tight coupling — two different things share a parent because they share a method.
- Deep inheritance hierarchies become unreadable: you must trace 5 levels to understand any one method.
- Data-heavy pipelines (pandas, numpy, ETL) are cleaner with functions than with object hierarchies.
- Go, Rust, Haskell — languages with no inheritance at all produce production-quality systems.

**Failure cases.**

- Java EJB 2.x: 7+ files and 400 lines of boilerplate for a 5-line business rule (1999–2004) — Java 2 Enterprise Edition mandated EJBs for any server-side logic. A single 'User' entity required: Home interface, Local interface, Remote interface, Bean implementation class, and XML deployment descriptor — before writing any business logic. Deep inheritance from EJB base classes enforced by the spec. Rod Johnson documented this in 'Expert One-on-One J2EE Design and Development' (Wrox, 2002) as an industry-wide failure of interface/inheritance dogma. He built Spring Framework specifically to eliminate it. By 2004 Spring had wider adoption than the official J2EE spec; EJB 3.0 (2006) rewrote the spec to adopt Spring's approach.

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Composition over Inheritance** — _GoF (Gang of Four), Design Patterns (1994)_
  > The GoF book itself recommends preferring composition — the patterns that made OOP famous mostly avoid deep inheritance.
- **Favour composition over inheritance** — _Joshua Bloch, Effective Java (2001), Item 16_
  > Inheritance is appropriate only in is-a relationships. Reuse via composition is safer and more flexible.
- **Functional Programming renaissance** — _Haskell, Clojure, Elm, Rust communities — 2010s_
  > Type classes, traits, and algebraic data types achieve polymorphism without inheritance. The paradigm works at production scale.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- True is-a hierarchies: GUI widgets, plugin frameworks, protocol implementations.
- Team is homogeneous in OOP experience and the domain maps naturally to objects.
- Framework demands it (Django models, Flask extensions).

_Break the dogma when:_

- Inheritance is used for code reuse, not is-a modelling.
- Subclasses override most parent methods — the hierarchy is not earning its keep.
- Mixins are piling up to compose behaviors — that is composition with extra confusion.
- Data-heavy code: functions over dataclasses are clearer than method-heavy classes.

**Main signal:** You cannot add a new subclass without reading and understanding the full parent chain. That is coupling, not extensibility.

**Related tags:** `deep-inheritance`.

## §6. TDD (Test-Driven Development) 🎯  \[filled\]

**Definition.** Red-Green-Refactor. Write the test first, then the code.

**Origin.** Kent Beck.

**Failure conditions.**

- Unknown domain — you don't yet know what the API should look like.
- UI code, visualizations.
- Research / exploratory coding.

**Failure cases.**

- [DHH/Basecamp: over-mocked TDD test suite that passed but missed integration bugs (2014)](https://dhh.dk/2014/tdd-is-dead-long-live-testing.html) — Basecamp's codebase accumulated tests designed for TDD purity: controllers mocked to avoid touching the database, models mocked to avoid touching controllers, every class given an interface to enable injection. Tests ran fast and passed. Integration bugs multiplied — the mocked boundaries didn't match the real ones. DHH published 'TDD is Dead. Long live testing.' and the team moved to higher-level system tests that actually caught bugs. Lesson: test isolation can create a false safety signal when the mocks don't model the real integration points.

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Spike First** — _Kent Beck, «Extreme Programming Explained» (1999)_
  > In an unknown domain, first a spike (throwaway prototype without tests), then discard it, then rewrite with TDD.
- **Test After / Test Last** — _folk, counter-practice_
  > Tests are written after implementation, when the API has stabilized. Domain: UI, exploratory, research.
- **Characterization Testing** — _Michael Feathers, «Working Effectively with Legacy Code» (2004)_
  > For legacy without tests: test locks in current behavior so you can refactor safely.
- **TDD is dead. Long live testing.** — _DHH (David Heinemeier Hansson), 2014_ ([source](https://dhh.dk/2014/tdd-is-dead-long-live-testing.html))
  > TDD as ideology led to over-mocking and designing for tests instead of designing for the problem.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- You already understand the domain and roughly know what the API should look like.
- Working on stable business logic you plan to refactor.
- Cost of a production error is very high (finance, security, medicine, billing).

_Break the dogma when:_

- You're in an unknown domain — use Spike First.
- Working with UI, complex visual states, or external integrations — Test After.
- Working with legacy without tests — Characterization Testing.
- Prototype / proof of concept that will be thrown away in a week.

**Main signal:** You write a test before you understood what the code should do. Result — well-tested wrong design + a forest of mocks.


## §7. SOLID as Law  \[draft\]

**Definition.** SRP, OCP, LSP, ISP, DIP — five principles all code must follow.

**Origin.** Uncle Bob, 2000s.

**Failure conditions.**

- SRP interpreted too narrowly: micro-classes with one method each; a single feature touches 20 files.
- OCP applied pre-emptively: extension points for behaviours that never change add dead abstraction.
- DIP everywhere: an interface for every class even when only one implementation exists.
- ISP applied too early: explosion of tiny interfaces that mirror exactly one caller.
- SOLID used as a checklist to pass code review rather than as a tool for solving real coupling problems.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Simple Design (Beck 4 Rules)** — _Kent Beck, Extreme Programming Explained (1999)_
  > Passes tests; communicates intent; no duplication; fewest elements. SOLID emerges from this naturally — it is not a starting constraint.
- **CUPID — properties over principles** — _Dan North, 2022_ ([source](https://dannorth.net/cupid-for-joyful-coding/))
  > SOLID is too prescriptive. CUPID (Composable, Unix-philosophy, Predictable, Idiomatic, Domain-based) describes properties of good code, not rules to enforce.
- **Shotgun Surgery anti-pattern** — _Martin Fowler, Refactoring (1999)_
  > Over-applying SRP produces shotgun surgery: a single change scatters edits across many files. The smell has a name — it is a known failure mode of excessive decomposition.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Large codebase with multiple teams — stable boundaries prevent cross-team coupling.
- Extension points that genuinely exist: multiple payment providers, multiple storage backends.
- Team explicitly needs shared vocabulary for code review.

_Break the dogma when:_

- Single-person or two-person project — overhead of interfaces and injection is not justified.
- CRUD application where the domain rarely changes.
- Early prototype: applying OCP/DIP before the abstractions are proven produces the wrong design.
- Checklist-driven reviews: SOLID as a gate for merges degrades into cargo-culting.

**Main signal:** Adding a new feature requires creating an interface, an implementation, a factory, and a registration entry — but there is only one implementation and there never will be a second.


## §8. Self-documenting code (no comments needed)  \[draft\]

**Definition.** Good code reads without comments. Comments are a sign of unclear code.

**Origin.** Uncle Bob, Clean Code.

**Failure conditions.**

- Domain knowledge that code cannot convey: why this algorithm was chosen over alternatives.
- Non-obvious invariants: this function assumes X has already been called.
- Performance tricks that look wrong but are intentionally correct.
- Regulatory requirements or legal constraints that require prose explanation.
- The rule becomes remove all comments even when the WHY is genuinely non-obvious.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Comment the WHY, not the WHAT** — _The Pragmatic Programmer, Hunt and Thomas (1999)_
  > Comments explaining intent, constraints, and tradeoffs are valuable. Comments restating the code are noise. The distinction is the point — not no comments.
- **Literate Programming** — _Donald Knuth, 1984_
  > Code and prose belong together. Complex algorithms need mathematical explanations that code syntax cannot provide.
- **Architecture Decision Records** — _Michael Nygard, 2011_ ([source](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions))
  > The most critical documentation is not inside functions — it is the decision log explaining why the system is shaped the way it is.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Naming is rich enough to express intent: domain concepts map clearly to identifiers.
- Team shares deep domain knowledge — no onboarding gap that prose would close.
- Code is straightforward CRUD or data transformation with no non-obvious correctness requirements.

_Break the dogma when:_

- The WHY is genuinely non-obvious: performance constraints, workarounds, legal obligations.
- Algorithm has non-obvious correctness requirements (cryptography, numerical stability, concurrency).
- Team turns over and onboarding time matters — good comments reduce the knowledge cliff.
- An invariant cannot be expressed as a type or a name: add a comment.

**Main signal:** A new team member reads the function and understands WHAT it does, but not WHY it exists, WHY this approach, or WHY the seemingly wrong constant is correct.


## §9. Premature optimization is the root of all evil  \[draft\]

**Definition.** Don't optimize until you've profiled. (Usually cited without context.)

**Origin.** Donald Knuth, 1974. Full quote: We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil. Yet we should not pass up our opportunities in that critical 3%.

**Failure conditions.**

- The quote is weaponised to avoid thinking about performance entirely — we will optimise later becomes never.
- Ignores Knuth's own 3%: structural decisions (O(n^2) vs O(n log n)) are design, not premature optimisation.
- Retry counts, connection pool sizes, timeout values — foundational, not premature.
- Latency as a product constraint from day 1 (trading systems, real-time games) — not a post-hoc concern.
- The culture becomes always defer and the team never develops performance intuition.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Profile-Driven Development** — _Brendan Gregg, Systems Performance (2013/2020)_
  > The correct reading of Knuth is: measure first, then optimise the bottleneck. The tool is profiling, not the quote.
- **Algorithmic thinking is design, not optimisation** — _folk (CS pedagogy)_
  > Choosing O(n log n) over O(n^2) is not premature optimisation — it is selecting the right algorithm. Conflating the two is a misreading of Knuth.
- **Performance budgets** — _Google Web Vitals / Lighthouse team_
  > For user-facing latency, performance is a feature constraint defined upfront, not an optimisation discovered post-launch.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- You have correct, readable code and no profiling data — do not optimise yet.
- Code clarity is genuinely at stake: the optimisation makes the code harder to reason about.
- The hotpath has not been identified — any guess about where time is spent is probably wrong.

_Break the dogma when:_

- You are choosing between algorithms: O(n^2) vs O(n log n) is a design decision, not an optimisation.
- Latency budget is a product constraint defined before writing any code.
- You have profiling data showing a specific bottleneck — now optimise that bottleneck deliberately.
- Infrastructure constants (timeouts, pool sizes, batch sizes) must be sized correctly from the start.

**Main signal:** The codebase has no performance tests, no profiling history, and the team calls every performance concern premature. The quote has become a reason not to think.


## §10. Functional purity / Immutability everywhere  \[draft\]

**Definition.** Avoid mutations. Pure functions. No side effects.

**Origin.** Haskell community, FP renaissance of the 2010s, React/Redux.

**Failure conditions.**

- Immutability + large data structures leads to garbage collection pressure (copy-on-write overhead).
- Pure FP in inherently stateful systems (web servers, UIs, databases) adds monad-wrapping indirection.
- Monad chains for IO in non-Haskell languages (Python, JS) become harder to read than equivalent imperative code.
- Go, Python, JavaScript: pure FP style is non-idiomatic and creates friction for developers joining the team.
- Redux-everywhere in UIs: global immutable state for local component state that changes many times per second.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Practical Functional Programming** — _Scott Wlaschin, F# for Fun and Profit (2012-present)_ ([source](https://fsharpforfunandprofit.com/))
  > Apply functional style where it pays off (data transformations, business rules); use mutation where it is the natural model (state machines, I/O).
- **Object-Functional hybrids** — _Scala, Kotlin communities_
  > Immutable value objects for domain logic + mutable infrastructure code. Neither pure OOP nor pure FP — pragmatic composition.
- **Local mutation is fine** — _Effective Python, Brett Slatkin; Rust ownership model_
  > Mutation scoped to a function body (local variable reassignment, list building then return) has no observable side effect. Immutability matters at the boundary, not inside a local scope.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Pure business logic computation: data transformations, validations, calculations — benefit from testability and referential transparency.
- Shared mutable state is causing bugs — immutability is the surgical fix.
- Concurrent code where shared mutation causes races.

_Break the dogma when:_

- Inherently stateful domain: session management, stream processing, event loops.
- Immutability overhead (copy-on-write) is measurable in profiling data.
- Team is unfamiliar with FP idioms — forcing purity creates unreadable code that nobody maintains.
- Framework requires mutation (ORM, UI component state).

**Main signal:** Every function that has a side effect wraps it in a monad or callback chain. The type system is correct; the code is unreadable.

**Related tags:** `mutable-default-arg`.

## §11. KISS (Keep It Simple, Stupid)  \[draft\]

**Definition.** Prefer simple solutions over complex ones. Complexity is the enemy. Remove everything that isn't strictly necessary.


**Origin.** U.S. Navy, 1960. Kelly Johnson (Lockheed Skunk Works) insisted aircraft be repairable in combat with basic tools. Software adoption via Unix philosophy («Do one thing well») and later «Clean Code» culture.


**Failure conditions.**

- KISS used as a reason to avoid thinking deeply about the problem.
- Simplicity of implementation confused with simplicity of the model.
- Removing real complexity that the domain actually has — just hiding it elsewhere.
- Team conflates 'familiar' with 'simple'.
- 'Stupid' in the slogan is taken literally — optimizing for the dumbest solution, not the clearest one.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **Simple but Smart = Genius** — _Yegor Gaidar, 2026 (ArchDogma issue ARC-222)_
  > KISS without intelligence produces dumb simplicity. Real mastery is achieving simple interfaces over genuinely complex systems — not pretending complexity doesn't exist. Minecraft: one voxel, infinite depth. Einstein: «Everything should be made as simple as possible, but not simpler.»

- **Simple Made Easy** — _Rich Hickey, Strange Loop 2011_ ([source](https://www.infoq.com/presentations/Simple-Made-Easy/))
  > «Simple» (few interleaved concerns) ≠ «easy» (familiar/convenient). Easy solutions can be complected. The goal is simplicity of the model, not ease of the implementation.

- **Worse Is Better** — _Richard Gabriel, 1989_ ([source](https://www.dreamsongs.com/WIB.html))
  > The «New Jersey style» — simple implementation, imperfect interface — often wins in practice over the «MIT style» correct-interface design. A warning that KISS can be weaponized to ship deliberately incomplete things.


**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- Two designs solve the same problem — pick the one with fewer moving parts.
- Complexity is coming from your design choices, not from the domain.
- You can remove something and the system still correctly handles all real cases.

_Break the dogma when:_

- The problem is genuinely complex — KISS doesn't simplify the problem, just hides it.
- You're simplifying the wrong layer (impl) while complicating the right one (API/model).
- The 'simple' solution requires callers to carry the complexity you refused to encode.
- You're optimizing for lines of code, not for conceptual clarity.

**Main signal:** Every new edge case requires a workaround in the calling code. Your 'simple' core is pushing complexity outward — that's not KISS, that's a tax on every consumer.



## §12. Every User Request is a Feature (Scope Creep)  \[draft\]

**Definition.** Every user request gets implemented. Every interesting idea becomes a milestone. The product grows continuously.

**Origin.** Early startup culture: 'we need to be everything to everyone'. Reinforced by agile backlogs with no pruning discipline.

**Failure conditions.**

- Product becomes too complex for any user to understand fully.
- Core workflow gets slower as peripheral features add cognitive load.
- Engineering velocity collapses as every new feature requires touching 12 other features for compatibility.
- Team loses track of what the product actually is.
- Initial user segment (who loved the focused product) churns as the product bloats.

**Failure cases.**

- QuackNet DePIN platform: Wi-Fi probe network → Solana + Kafka + ClickHouse + AI in 8 months — QuackNet started as a focused tool: crowdsource Wi-Fi quality data from mobile devices. Within 8 months it expanded to: Solana blockchain for token rewards, Kafka for real-time ingestion, ClickHouse for analytics, on-device AI for signal quality estimation, and a validator monitoring network. Each feature was individually interesting. The product lost its original focus. The core Wi-Fi probe — the thing users actually understood — became buried under protocol complexity. First-party postmortem.

**Counter-dogmas.**

- **Feature pruning** — _Jason Fried & DHH, 'Getting Real' (2006)_
  > Half a product, not a half-assed product. Build half the features, but make them excellent. Prune aggressively — the product you ship to new users is the product they see first.
- **Jobs To Be Done** — _Clayton Christensen, 'The Innovator's Dilemma' (1997); popularised by Bob Moesta_
  > Users hire a product to do a specific job. When a product tries to do every job, it does none of them well. Define the primary job ruthlessly and protect it.

**Honest verdict** \[draft_awaiting_cases\].

_Follow the dogma when:_

- The new feature serves the same user job as the core product.
- The product is in early discovery and you genuinely don't know what the core job is yet.
- You have evidence that the requested feature is the blocking reason users don't adopt.

_Break the dogma when:_

- The team is excited about the feature but can't name a user who asked for it.
- The feature serves a different user segment than the current product.
- Engineering time on the feature exceeds engineering time on the core product.
- The feature requires explaining to new users before they can understand the product.

**Main signal:** Your onboarding documentation gets longer with every release. New users need more context to understand the product than they did 6 months ago. That is not product growth — that is product obesity.


## Candidates

Anti-patterns and dogmas-in-observation. No §-number; can be promoted to `dogmas` once enough cases accumulate.

### God File / God Class  \[god-class\]

Anti-pattern consequence, not a dogma. Appears from fear of refactoring + no tests + deadlines.

**Sources.**

- [SQLite amalgamation — deliberate performance decision (~238k lines)](https://sqlite.org/amalgamation.html)
- [Knight Capital 2012 — $440M from dead code in legacy](https://www.sec.gov/litigation/admin/2013/34-70694.pdf)
- Michael Feathers, «Working Effectively with Legacy Code» (2004)

**Related tags:** `god-function`, `god-class`, `long-function`.

### Long Parameter List  \[long-parameter-list\]

Classic code smell — when a signature demands too much, it can usually be split into a parameter object, keyword-only namespace, or two different functions.

**Sources.**

- Martin Fowler, «Refactoring» (1999/2018) — Long Parameter List
- Robert C. Martin, «Clean Code» (2008): «Three arguments should be avoided where possible. More than three requires very special justification.»

**Related tags:** `too-many-params`.

### YAGNI (You Aren't Gonna Need It)  \[yagni\]


### Agile and its rituals  \[agile-rituals\]


### Configuration over code  \[config-over-code\]


### Serverless for everything  \[serverless-everything\]


### GraphQL over REST  \[graphql-over-rest\]


### NoSQL over SQL  \[nosql-over-sql\]


### Event Sourcing  \[event-sourcing\]


### Domain-Driven Design as mandatory practice  \[ddd-mandatory\]


### Code reviews must always be mandatory  \[code-reviews-mandatory\]


### Feature flags over branches  \[feature-flags-over-branches\]


### Monorepo vs polyrepo  \[monorepo-vs-polyrepo\]


### Pair programming always  \[pair-programming-always\]


### Broad exception handling (bare except / except Exception)  \[broad-exception-handler\]

Swallowing unexpected exceptions hides bugs. Specific handlers communicate intent and preserve error information.

**Sources.**

- [PEP 8 — Avoid bare except clauses](https://peps.python.org/pep-0008/#programming-recommendations)
- pylint W0703 — Catching too general exception
- [flake8-bugbear B001 — bare except](https://github.com/PyCQA/flake8-bugbear)

**Related tags:** `broad-except`.

### Mutable Default Argument  \[mutable-default-argument\]

Classic Python gotcha: mutable default values (list, dict, set) are shared across all calls. Use None as sentinel.

**Sources.**

- [Python docs — Default Argument Values](https://docs.python.org/3/faq/programming.html#why-are-default-values-shared-between-objects)
- pylint W0102 — Dangerous default value
- [flake8-bugbear B006 — Do not use mutable data structures for argument defaults](https://github.com/PyCQA/flake8-bugbear)

**Related tags:** `mutable-default-arg`.

### Too Many Return Points  \[too-many-exits\]

Many return statements can signal a function handling too many cases. Related to the single-exit principle — a guideline, not a law.

**Sources.**

- Robert C. Martin, Clean Code (2008) — single exit point
- pylint R0911 — Too many return statements (default: 6)

**Related tags:** `too-many-returns`.

---

## Contributing

Source of truth — `catalog/dogmas.yaml`. All edits go there; this
file is regenerated via `archdogma render-catalog`.
If you spot a discrepancy between YAML and .md — someone forgot to regenerate.
Report a bug; do not edit `.md` by hand.
