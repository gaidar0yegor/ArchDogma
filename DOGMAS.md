<!-- AUTO-GENERATED from catalog/dogmas.yaml — DO NOT EDIT BY HAND. Run: archdogma render-catalog -->

# Dogma Catalog

_Updated: 2026-08-11 — schema v1._

Catalog rules:

- Every claim has a source. Without a source — `honesty-bug`.
- Every counter-dogma has `attribution`. Without an author — also `honesty-bug`.
- A dogma marked 🎯 v0.1-priority must have status no lower than `draft`.
- Absence of a tag ≠ absence of a problem.

## §1. 100% Test Coverage  \[filled\]

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
- [IG: test-everything culture had developers building elaborate harnesses for trivial glue code (Daniel Lebrero, 2016)](https://danlebrero.com/2016/05/18/tragedy-100-code-coverage/) — Lebrero, an architect at IG writing first-hand on its engineering blog: "Why did you write that test?" One developer asked for help using Mockito to unit-test initialisation code that was pure glue — no conditionals, no loops, no transformations — and insisted on writing the test after being told it was unnecessary. Another proudly showed high coverage achieved through an extensive Cucumber/BDD harness whose supporting code existed to test a simple map lookup — "a big waste of time" with "nothing to do with BDD". The tragedy, he writes, is bright developers producing pointless tests "that will need to be maintained by future generations". His counter-advice: try 100% coverage on one project to learn where the limit is, then stop and think instead of applying the practice mechanically.
- [Coverage tied to maturity levels, gamed by shredding functions — design degraded while the score rose (James O. Coplien, 2014)](https://gist.github.com/ktzar/596ee5aae7c41f2e585331e4b71d1e2c) — In "Why Most Unit Testing is Waste", Coplien documents a client where developers "were required to have 40% code coverage for Level 1 Software Maturity, 60% for Level 2 and 80% for Level 3", some "aspiring to 100% code coverage". The mandate was met by gaming: "Large functions for which 80% coverage was impossible were broken down into many small functions for which 80% coverage was trivial" — the corporate maturity score rose within a year ("you will certainly get what you reward") while the design degraded as functions stopped encapsulating algorithms. Nuance kept honest: the mandated thresholds were 40/60/80 with 100% as aspiration, not policy. Provenance note: the paper's canonical host (rbcs-us.com) is DNS-dead; the URL is a verified full-text mirror, and an Internet Archive capture of the original PDF exists.

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


## §2. Clean Architecture / N Layers of Abstraction  \[filled\]

**Definition.** Split code into layers (domain, application, infrastructure, presentation). Dependencies point inward.

**Origin.** Uncle Bob, Clean Architecture. Previously Hexagonal/Onion Architecture.

**Failure conditions.**

- Significant upfront boilerplate: interfaces, adapters, DTOs, mappers — before any business value.
- Mapping overhead between layers multiplies the surface area for bugs.
- Premature for small teams building simple CRUD apps — architecture tax before architecture benefit.
- Confuses structure with discipline: teams add layers but couple them anyway.
- Testing becomes harder when every boundary needs a mock or fake.

**Failure cases.**

- [Fifteen layers of data-copying, mandated by a consultant — Johannes Brodwall's client review (2014)](https://johannesbrodwall.com/2014/07/10/the-madness-of-layered-architecture/) — Brodwall visited a team whose application had fifteen layers: displaying data from the database on a web page passed it through 15 classes, most of which did nothing but copy data from one object to the next, with validation logic scattered inconsistently across layers. The team had built it that way because an expensive consultant told them to — asked for the rationale, "they just shrugged". His named costs: dead-weight code, layer classes that become low-coherence "functionality magnets", unclear extension points, and trivial features paying the same infrastructure tax as complex ones. His counter-rule: build outside-in, inject data access directly where that suffices — "most problems in software engineering can be solved by removing a misplaced layer." The client is anonymised (standard consulting practice); the 15-layer figure and the consultant mandate are stated explicitly in the post.
- [Jimmy Bogard: onion architecture on a long-term project — 'within a couple of months, the cracks started to show' (writeup 2018)](https://www.jimmybogard.com/vertical-slice-architecture/) — Bogard (AutoMapper, MediatR) writes that his team started a long-term project built around an onion architecture with enforced inward-pointing dependencies, and "within a couple of months, the cracks started to show around this style." The policy produced abstractions around things that should not be abstracted ("Controller MUST talk to a Service that MUST use a Repository"); organising by technical layer meant every feature change touched many layers, plus the mock-heavy testing every enforced boundary invites. His note that the layered rules are "really only appropriate in a minority of the typical requests in a system" is the failure condition of this dogma stated from experience. The team switched to vertical slices — "minimize coupling between slices, maximize coupling in a slice" — and used that exclusively for the following 7-8 years. His caveat travels with the case: slices demand a team skilled at spotting smells and refactoring, rather than leaning on upfront structure.

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

**Related tags:** `circular-import`, `unstable-dependency`.

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
  > Optimize for change first. Prefer duplication until the abstraction is obvious — a hasty abstraction is costlier than repeated code.

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

**Related tags:** `wrong-abstraction`, `hub-module`.

## §4. Microservices for Everything 🎯  \[filled\]

**Definition.** Monolith is evil. Cut the system into small services.

**Origin.** Netflix, Amazon, ThoughtWorks, ~2014.

**Failure conditions.**

- Team < 10 people.
- One product, not independent business units.
- Distributed transactions become the norm.
- Debug takes 3 hours because traces scatter across 12 services.

**Failure cases.**

- [Segment: 140+ destination microservices folded back into one monolithic service (Alexandra Noonan, 2018)](https://segment.com/blog/goodbye-microservices/) — Segment ran 140+ individual destination services, one per integration (Salesforce, Mixpanel, ...), each duplicating routing and retry logic; on-call engineers could not hold the system in their heads. Alexandra Noonan's first-party writeup describes folding the per-destination services back into a single monolithic destination service. Centrifuge, often misremembered as "the monolith", was the new queue/traffic infrastructure that replaced the per-destination queues feeding it — not the consolidated service itself. Ops burden dropped and delivery reliability improved. URL note: segment.com now redirects this post to twilio.com (Segment's owner); the article is intact at the new host. This entry previously said "2022" and misattributed Centrifuge — found by our own pre-launch audit; the case stands, our metadata was wrong.
- [Amazon Prime Video: serverless microservices → single process, 90% cost reduction (2023)](https://web.archive.org/web/2023/https://www.primevideotech.com/video-streaming/scaling-up-the-prime-video-audio-video-monitoring-service-and-reducing-costs-by-90) — Prime Video's audio/video monitoring was built as serverless microservices for elasticity. Data passed between steps via S3 — storage and retrieval costs became the dominant cost. Merging into a single process eliminated the S3 round-trips and cut infrastructure cost by 90%. Latency improved. The distributed architecture had solved a scaling problem that didn't exist at their actual volume.

**Success cases.**

- Netflix, Amazon (at a certain scale) — Need specific post-mortem links with numbers.

**Counter-dogmas.**

- **MonolithFirst** — _Martin Fowler, 2015_ ([source](https://martinfowler.com/bliki/MonolithFirst.html))
  > Almost all successful microservice systems started as monoliths and were split later.
- **Modular Monolith** — _Shopify and others_
  > Modules with clear boundaries inside one process. No network boundaries, but with the ability to split later.
- **Prime Video monolith migration** — _Amazon Prime Video Tech Blog, 2023_ ([source](https://web.archive.org/web/2023/https://www.primevideotech.com/video-streaming/scaling-up-the-prime-video-audio-video-monitoring-service-and-reducing-costs-by-90))
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


## §5. OOP as the Only Truth (inheritance everywhere)  \[filled\]

**Definition.** Everything is an object. Inheritance is the primary tool for reuse.

**Origin.** Smalltalk, Java, GoF Design Patterns.

**Failure conditions.**

- Fragile Base Class problem: a change to the parent silently breaks all children.
- Inheritance for code reuse creates tight coupling — two different things share a parent because they share a method.
- Deep inheritance hierarchies become unreadable: you must trace 5 levels to understand any one method.
- Data-heavy pipelines (pandas, numpy, ETL) are cleaner with functions than with object hierarchies.
- Go, Rust, Haskell — languages with no inheritance at all produce production-quality systems.

**Failure cases.**

- Java EJB 2.x: spec-mandated interfaces and boilerplate for every entity (1999-2004) — J2EE culture mandated EJBs for server-side logic. A remotely-accessed entity bean required a Home interface, a Remote interface, the bean implementation class and an XML deployment descriptor (EJB 2.0 added the LocalHome/Local pair for in-process access) — before any business logic. Precision note from our own audit: the tax here was spec-enforced INDIRECTION and boilerplate — beans implementing framework interfaces and lifecycle callbacks — rather than deep inheritance chains; the case sits under this dogma for the "framework object model as the only truth" failure mode. Rod Johnson documented the cost in "Expert One-on-One J2EE Design and Development" (Wrox, 2002) and built Spring specifically to eliminate it; EJB 3.0 (2006) rewrote the spec in Spring's image.
- [Neversoft's Tony Hawk games: the industry-standard inheritance hierarchy became a 'blob' that took two years to unwind (Mick West, 2007)](https://cowboyprogramming.com/2007/01/05/evolve-your-heirachy/) — West, Neversoft co-founder, describes the then-standard game-industry rule — a deep game-object inheritance hierarchy — degenerating over three successive Tony Hawk titles into the blob anti-pattern: simple objects like rocks and grenades carried unneeded data and behaviour inherited from ancestors, functionality was duplicated across branches because it could not be shared sideways, the player class accumulated outsized complexity, and unneeded inherited behaviour cost performance. The fix — component-based composition — took approximately two years, because the studio shipped a title every year on the same codebase, and initially met resistance from programmers used to inheritance. Afterward designers could compose new object types data-driven. First-person account by the engineer who did the refactor, on a shipped multi-title commercial codebase.
- [Django's class-based views: inheritance/mixins as the official reuse API made real views longer and harder to debug (Luke Plant, 2012)](https://lukeplant.me.uk/blog/posts/djangos-cbvs-were-a-mistake/) — Django made class-based views — inheritance plus mixin chains — the framework's official reuse mechanism for views. Plant, a Django core developer since 2006, shows with measured code that a realistic contact-form view is 24 non-blank lines as a CBV versus 17 as a plain function, despite brevity being the selling point. His verdict: CBVs make trivial views slightly shorter and medium-complexity views significantly longer and much harder to debug, because behaviour is scattered across hook methods (get_initial, get_form_class, get_context_data) with repetitive super() calls, and multiple inheritance produces confusing method-resolution-order problems. An insider critique of inheritance-as-primary-reuse applied as API policy in one of the most widely used web frameworks; he later expanded it into "Django Views — The Right Way".

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

- [DHH: "Test-first units leads to an overly complex web of intermediary objects" — a first-person renunciation (2014)](https://dhh.dk/2014/tdd-is-dead-long-live-testing.html) — Verbatim from the essay: "Test-first units leads to an overly complex web of intermediary objects and indirection in order to avoid doing anything that's 'slow'. Like hitting the database. Or file IO... It's given birth to some truly horrendous monstrosities of architecture. A dense jungle of service objects, command patterns, and worse." His stated practice after renouncing test-first: test Active Record models directly against the database with fixtures, and move emphasis toward "slow, system tests" via Capybara. Scope note, per this catalog's rules: this is an opinion essay and first-person account by the named responsible engineer — it names the failure mode from experience but reports no incident numbers, and it is labelled accordingly. An earlier version of this entry invented Basecamp specifics the essay does not contain; our own pre-launch audit caught it.
- [Ron Jeffries test-drives a Sudoku solver into a dead end; Norvig solves it with domain knowledge (2006) — and Jeffries disputes the moral (2022)](https://ronjeffries.com/xprog/articles/oksudoku/) — Jeffries — XP co-creator, Agile Manifesto signatory — began a five-part series test-driving a Sudoku solver in Ruby, red-green-refactor from the first failing test. By part 5 he was still refactoring the board representation, his forced-moves strategy had solved exactly one puzzle, and the series stopped without a working general solver. The same year Peter Norvig published "Solving Every Sudoku Puzzle" (norvig.com/sudoku.html): constraint propagation plus depth-first search in about a page of Python, solving the hardest puzzles in ~0.01s. The contrast made this the canonical example of test-first incrementalism stalling in an unknown algorithmic domain where the missing ingredient was domain insight, not more tests. The caveat travels with the case, per this catalog's rules: in a 2022 retrospective (ronjeffries.com/articles/-z022/01121/sudoku-again/) Jeffries concedes "you could say that I failed" but disputes the moral — "I didn't do very much in the way of TDD" — and says reading up on Sudoku solving first would have helped. Present it as: test-first in an unknown domain stalled; the author attributes the failure to missing domain knowledge.
- [Coplien: unit-test-mass from TDD-as-policy — suites more complex than the code, or quietly switched off (2014)](https://gist.github.com/ktzar/596ee5aae7c41f2e585331e4b71d1e2c) — From "Why Most Unit Testing is Waste", on shops "following what they call test-driven development". Richard Jacobs at Sogeti reported his team's unit tests had become more complex than the code under test. At Coplien's own earlier job in Denmark — a project heavily based on XP and unit testing — he finally got a clean Maven build only to find the unit tests failing, and was told the standard practice was to invoke Maven with a flag that turns those tests off: a test-first suite rotted in place while nominally still the safety net. His field remedy: audit the suite and throw away tests that have not failed in a year, keeping verification at integration/system level. Scope note: this targets the unit-test-mass consequence of TDD as policy, not the red-green-refactor loop itself. Provenance: canonical host (rbcs-us.com) is DNS-dead; the URL is a verified full-text mirror.

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


## §7. SOLID as Law  \[filled\]

**Definition.** SRP, OCP, LSP, ISP, DIP — five principles all code must follow.

**Origin.** Uncle Bob, 2000s.

**Failure conditions.**

- SRP interpreted too narrowly: micro-classes with one method each; a single feature touches 20 files.
- OCP applied pre-emptively: extension points for behaviours that never change add dead abstraction.
- DIP everywhere: an interface for every class even when only one implementation exists.
- ISP applied too early: explosion of tiny interfaces that mirror exactly one caller.
- SOLID used as a checklist to pass code review rather than as a tool for solving real coupling problems.

**Failure cases.**

- [Dan North: DIP-as-law produced 'shadow codebases' of one-interface-per-class across J2EE/Spring-era clients (talk 2016, writeup 2021)](https://dannorth.net/blog/cupid-the-back-story/) — First-person writeup of North's PubConf London talk "Why Every Element of SOLID is Wrong", drawing on ~30 years of consulting. On DIP applied to every dependency via wiring frameworks (J2EE, OSGi, Spring), he reports seeing "entire shadow codebases where each class is backed by exactly one interface, which only exists to satisfy a wiring framework or to inject a mock or stub" — and the promised payoff ("you can just swap out the database") "evaporates as soon as you try to". He calls SRP the "Pointlessly Vague Principle": artificial splitting of code that changes together. His "billions of dollars in sunk cost" line is rhetoric, not a measurement — cited here as testimony about a pattern he saw repeatedly, not as data. His alternative became the CUPID properties (2022).
- [Mark Seemann: one-interface-per-class 'loose coupling' yields fake abstractions — a practice he had been guilty of himself (2010)](https://blog.ploeh.dk/2010/12/02/Interfacesarenotabstractions/) — Seemann (author of "Dependency Injection in .NET") documents the mechanical interface-extraction habit through which DIP was operationalised in .NET shops, aided by Visual Studio's Extract Interface making "it very easy to do the wrong thing": "you probably have a 1:1 relationship between your interfaces and the concrete classes that implement them... I've been guilty of this and didn't like the result." His verdict: "Having only one implementation of a given interface is a code smell." Concrete costs: interfaces extracted from an ORM context that stay coupled to it so no second implementation is ever possible, wrapper interfaces existing only to enable mocking, and IFooFactory/IFooPolicyFactory hierarchies. Scope note: the post never uses the word SOLID — it documents the "DIP everywhere" failure mode, and is cited for exactly that.

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

**Related tags:** `unstable-dependency`.

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


## §9. Premature optimization is the root of all evil  \[filled\]

**Definition.** Don't optimize until you've profiled. (Usually cited without context.)

**Origin.** Donald Knuth, 1974. Full quote: We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil. Yet we should not pass up our opportunities in that critical 3%.

**Failure conditions.**

- The quote is weaponised to avoid thinking about performance entirely — we will optimise later becomes never.
- Ignores Knuth's own 3%: structural decisions (O(n^2) vs O(n log n)) are design, not premature optimisation.
- Retry counts, connection pool sizes, timeout values — foundational, not premature.
- Latency as a product constraint from day 1 (trading systems, real-time games) — not a post-hoc concern.
- The culture becomes always defer and the team never develops performance intuition.

**Failure cases.**

- [Joe Duffy (Microsoft, PLINQ): the Knuth quote used to hide 10-100x waste — teams parallelised for 8x instead of refactoring for 100x (2010)](https://joeduffyblog.com/2010/09/06/the-premature-optimization-is-evil-myth/) — Duffy ran the team that delivered PLINQ and wrote from inside the culture that practiced the dogma: the quote "is used to defend sloppy decision-making" and to defer performance thinking that then never happens. His first-hand observation: teams reached for parallelisation to get 8x speedups on expensive queries where, in his words, trivially refactoring to a slimmed-down algorithm would have sped the code up 100-fold — design-time performance thinking had been skipped, so hardware was thrown at an algorithmic problem. He also demonstrates the death-by-a-thousand-cuts mechanism with a measured LINQ-to-Objects example an order of magnitude slower than the equivalent loop (delegate allocations, closures, interface calls) — diffuse costs invisible to after-the-fact hotspot profiling. His prescription is Knuth's actual position: performance is thought about at design time, because architectural decisions cannot be profiled back out later.
- [Nelson Elhage (Stripe, Sorbet): Facebook's Flow needed a multi-year re-architecture for performance that Sorbet designed in on day 1 (2020)](https://blog.nelhage.com/post/reflections-on-performance/) — Elhage co-authored the Sorbet Ruby typechecker and addresses the aphorism directly, calling it "decent default advice" whose limitations are critical. His documented example targets the dogma's blind spot — architecture: Sorbet restricted itself to local-only type inference up front, a structural decision that was cheap to make and "would have been incredibly costly to change"; the Flow team, which had not, was at time of writing "in the middle of a multi-year refactor to move Flow and Facebook's code base to a more local-only model". He also documents why profile-then-fix fails on such systems: Sorbet's speed comes from diffuse costs — "very few hot spots; time is divided relatively evenly" — not from discrete hotspots a profiler would surface. Structural performance decisions are design, not premature optimisation.

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


## §10. Functional purity / Immutability everywhere  \[filled\]

**Definition.** Avoid mutations. Pure functions. No side effects.

**Origin.** Haskell community, FP renaissance of the 2010s, React/Redux.

**Failure conditions.**

- Immutability + large data structures leads to garbage collection pressure (copy-on-write overhead).
- Pure FP in inherently stateful systems (web servers, UIs, databases) adds monad-wrapping indirection.
- Monad chains for IO in non-Haskell languages (Python, JS) become harder to read than equivalent imperative code.
- Go, Python, JavaScript: pure FP style is non-idiomatic and creates friction for developers joining the team.
- Redux-everywhere in UIs: global immutable state for local component state that changes many times per second.

**Failure cases.**

- [Discord: BEAM-enforced immutability collapsed on large member lists — replaced with a mutable Rust NIF (2019)](https://discord.com/blog/using-rust-to-scale-elixir-for-11-million-concurrent-users) — Discord's real-time infrastructure runs on Elixir, where the BEAM enforces immutability: every "mutation" produces a new copy. Guild member lists needed a sorted structure holding hundreds of thousands of entries under constant mutation, and immutable structures collapsed at that scale — plain lists took 500-3,000µs per insert at just 5,000 items; their best pure-Elixir OrderedSet hit 19,000µs inserting near the front of 250,000 items. They abandoned purity for this hot path and wrote a mutable SortedSet as a Rust NIF, getting 0.61-3.68µs per operation at 1,000,000 items. First-party writeup by Matt Nowack (Discord). Scope note: the immutability was language-enforced rather than a written team policy — this is the cleanest documented instance of the copy-cost failure mode, cited for that mechanism.
- [Culture Amp: pure-FP Elm as the preferred frontend language (2016), retired over dual-ecosystem cost (2023)](https://kevinyank.com/posts/on-endings-why-how-we-retired-elm-at-culture-amp/) — Culture Amp made Elm — pure functional, enforced immutability, no side effects — its preferred language for new frontend code from 2016 and built entire products in it. The cost surfaced as organisational friction, not runtime failure: the design-system team maintained parallel React and Elm implementations of every component and the two diverged; adding Web Components would have meant "effectively adding a third view framework"; the Elm 0.18-to-0.19 migration took roughly a year of volunteer effort; and an acquisition made the codebase ~75% React overnight, leaving about six committed Elm advocates. With TypeScript covering the original type-safety appeal, Elm was moved to "contain" and retired. Written by Kevin Yank, who led both the adoption and the retirement.
- [Twitter Lite: every keystroke through the global Redux store cost ~200ms per keypress on low-end Android (2017)](https://medium.com/@paularmstrong/twitter-lite-and-high-performance-react-progressive-web-apps-at-scale-d28a00e780a3) — The Twitter Lite PWA followed the Redux-everywhere pattern: the tweet composer dispatched draft text to the global store on every keypress. On Android 5 devices each keypress cost nearly 200ms and the insertion point jumped, producing jumbled sentences as users typed. The fix broke the dogma for high-frequency local state — the draft moved into local component state, cutting overhead by over half — and dispatches were batched (roughly 16 renders down to 8 in their measured case). First-party lessons-learned by Paul Armstrong (Twitter Lite team). Scope note: the post criticises only global-store-for-keystroke-state and dispatch storms, not Redux or immutability in general — it is cited for exactly that failure mode.

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

## §11. KISS (Keep It Simple, Stupid)  \[filled\]

**Definition.** Prefer simple solutions over complex ones. Complexity is the enemy. Remove everything that isn't strictly necessary.


**Origin.** U.S. Navy, 1960. Kelly Johnson (Lockheed Skunk Works) insisted aircraft be repairable in combat with basic tools. Software adoption via Unix philosophy («Do one thing well») and later «Clean Code» culture.


**Failure conditions.**

- KISS used as a reason to avoid thinking deeply about the problem.
- Simplicity of implementation confused with simplicity of the model.
- Removing real complexity that the domain actually has — just hiding it elsewhere.
- Team conflates 'familiar' with 'simple'.
- 'Stupid' in the slogan is taken literally — optimizing for the dumbest solution, not the clearest one.

**Failure cases.**

- [Google GFS: single master chosen 'to simplify the overall design problem' — became the bottleneck the whole company engineered around (retrospective 2009)](https://queue.acm.org/detail.cfm?id=1594206) — Sean Quinlan, GFS tech lead, says the single-master design "was actually one of the very first decisions, mostly just to simplify the overall design problem" — a distributed master was deemed too hard to build in the year the three-person team had. Sized for hundreds of terabytes and a few million files, the design met tens of petabytes: the master (a few thousand ops/second, facing thousands of concurrent clients) became the bottleneck, and with all metadata in the master's memory, file count became the scarcest resource in Google's storage. The complexity did not disappear — it moved into every application: teams bundled small files into big ones, partitioned data across multi-cell setups with static namespace files, BigTable kept two transaction logs open to dodge write hiccups, and Gmail went multihomed partly "to hide the GFS problems" (Gobioff: "we just decided to push some of the complexity out to the applications"). Manual master failover could take a cell down for an hour. Google replaced the design with a distributed-master system. Quinlan is candid that the simple design was the right call for shipping fast — this entry documents what the simplification cost over the following decade. Note: ACM Queue bot-blocks automated fetchers (403); the page is live in a browser and archived (web.archive.org, 2009-08-13 capture of this URL).
- [Go: generics omitted for language simplicity (2009) — the complexity reappeared as duplication in every user codebase, reversed in Go 1.18 (2022)](https://go.dev/blog/why-generics) — Russ Cox framed the deliberate choice in "The Generic Dilemma" (2009): "do you want slow programmers, slow compilers and bloated binaries, or slow execution times?" Go launched having chosen slow programmers — the language stayed simple by omitting generics. Ian Lance Taylor's first-party writeup documents what that simplicity cost its users: identical functions hand-duplicated per type, each needing its own tests; interface{} workarounds where "we lose all the benefits of static typing"; reflection "so awkward to write and slow to run that few people do that"; code generators complicating every build. "In three years of Go surveys, lack of generics has always been listed as one of the top three problems to fix in the language." The avoided language-spec complexity reappeared inside every user codebase; the team reversed course and shipped generics in Go 1.18 (March 2022). A cost-of-policy case acknowledged and corrected by the team itself, not an outage.

**Success cases.**

- _need_data_

**Counter-dogmas.**

- **As simple as possible, but not simpler** — _attributed to Albert Einstein (paraphrase; attribution disputed)_
  > Simplicity is bounded from below by the domain's real complexity. Simple interfaces over genuinely complex systems are mastery; pretending the complexity does not exist just relocates it.

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



## §12. Every User Request is a Feature (Scope Creep)  \[filled\]

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
- [Microsoft Office: every release grew the menu-and-toolbar UI for ~15 years until it collapsed into the Ribbon rewrite (Jensen Harris, 2006)](https://learn.microsoft.com/en-us/archive/blogs/jensenh/ye-olde-museum-of-office-past-why-the-ui-part-2) — Harris, who led the Office UX team, documented the arc in his "Why the UI" series: Word 2.0 (1992) had under 100 commands and 2 toolbars; Word 6 jumped to 8 toolbars; Office 97 hit 18 toolbars and nearly doubled top-level menu commands — "more room meant more features", and the customer request list was "miles-long": the growth was policy. By Word 97 "we started to see signs that people were feeling less in control of the program"; the UI "had begun to feel bloated... like a suitcase stuffed to the gills". Office 2000's adaptive menus and rafted toolbars tried to hide the accumulated surface without removing any of it ("we just added more pockets") — both failed and were turned off. The bill for never subtracting: a ground-up UI replacement, the Office 2007 Ribbon. Part 3, verified, carries the bloat and pockets passages: learn.microsoft.com/en-us/archive/blogs/jensenh/combating-the-perception-of-bloat-why-the-ui-part-3

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

**Related tags:** `god-function`, `god-class`, `god-module`, `long-function`.

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


### Circular Dependency Between Modules  \[circular-dependency\]

Two or more modules that transitively import each other. Python often tolerates it at runtime, which is what makes it durable: the failure surfaces later, as an AttributeError on a half-initialised module when import order changes. The architectural reading is the more useful one — a cycle means the boundary between those modules is not real, whatever the directory layout claims. No postmortem yet; this is a candidate with sources, not a dogma with cases.

**Sources.**

- [Python FAQ — best practices for using import in a module (circular import failure modes)](https://docs.python.org/3/faq/programming.html#what-are-the-best-practices-for-using-import-in-a-module)
- Robert C. Martin — Acyclic Dependencies Principle, «Granularity» (C++ Report, 1996)
- pylint R0401 — cyclic-import

**Related tags:** `circular-import`.

### The Load-Bearing Wall — Code Nobody Dares Change  \[untouchable-legacy\]

A module that many others depend on and that has not been modified in years. The reading is genuinely ambiguous, and the tag says so: the same two numbers describe a mature utility that stopped changing because it was finished, and a module the team routes around because changing it breaks forty importers. Feathers' framing is the useful one — the property that makes code legacy is not its age but the absence of a safe way to change it. No postmortem yet; candidate.

**Sources.**

- Michael Feathers, «Working Effectively with Legacy Code» (2004) — legacy defined by the absence of tests that make change safe
- [Adam Tornhill, «Software Design X-Rays» (2018) — behavioural code analysis, change frequency crossed with structure](https://pragprog.com/titles/atevol/software-design-x-rays/)

**Related tags:** `load-bearing-wall`.

### Hotspot — Complexity Where the Code Actually Moves  \[change-hotspot\]

Complexity only costs where the code changes. A large, gnarly module that nobody edits is a museum piece; the same module edited weekly is where defects and delivery drag accumulate. This is not a dogma anyone preaches — it is the correction to the dogma that all complexity is equally worth refactoring. Ranked by churn percentile within the repository, because an absolute commit count does not transfer between a two-month project and a ten-year one.

**Sources.**

- [Adam Tornhill, «Your Code as a Crime Scene» (2015/2024) — hotspots as the intersection of complexity and change frequency](https://pragprog.com/titles/atcrime2/your-code-as-a-crime-scene-second-edition/)
- [Adam Tornhill, «Software Design X-Rays» (2018)](https://pragprog.com/titles/atevol/software-design-x-rays/)

**Related tags:** `churn-hotspot`.

### Logical Coupling — Files That Change Together Without Knowing It  \[logical-coupling\]

Two modules that keep appearing in the same commit while neither imports the other. The structure says they are unrelated; the commit history says maintaining one means maintaining the other. Typical causes are a parser and the schema it assumes, a client and the server contract it mirrors, or two implementations of one rule that was never extracted. The import edge is deliberately subtracted: coupling the structure already declares is documented, not hidden. Naive versions of this measure are famously noisy, so a commit touching many files contributes no pairs and files with very few revisions are excluded. No postmortem yet; candidate.

**Sources.**

- Gall, Hajek, Jazayeri — «Detection of Logical Coupling Based on Product Release History» (ICSM 1998), the original formulation
- [Adam Tornhill, «Software Design X-Rays» (2018) — temporal coupling, and why sweeping commits must be filtered out](https://pragprog.com/titles/atevol/software-design-x-rays/)

**Related tags:** `temporal-coupling`.

### Bus Factor — One Person Holds a Shared Dependency  \[bus-factor\]

A module many others import whose entire history has one author. The risk is not that the person leaves; it is that the knowledge needed to change the module safely was never written into the repository. Author identity comes from git's mailmap-resolved name, so inconsistent commit identities inflate diversity and shared bot accounts deflate it — the measure is of commit metadata, not of who actually understands the code.

**Sources.**

- [Avelino, Passos, Hora, Valente — «A Novel Approach for Estimating Truck Factors» (ICPC 2016)](https://arxiv.org/abs/1604.06766)
- Michael Feathers, «Working Effectively with Legacy Code» (2004) — knowledge that lives outside the code

**Related tags:** `single-author-hub`.

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
