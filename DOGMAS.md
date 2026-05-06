<!-- AUTO-GENERATED from catalog/dogmas.yaml — DO NOT EDIT BY HAND. Run: archdogma render-catalog -->

# Каталог догм

_Обновлено: 2026-04-30 — schema v1._

Правила каталога:

- Каждое утверждение имеет источник. Без источника — `honesty-bug`.
- Каждая контр-догма имеет `attribution`. Без автора — тоже `honesty-bug`.
- Догма, помеченная 🎯 v0.1-priority, обязана иметь статус не ниже `draft`.
- Отсутствие тега ≠ отсутствие проблемы.

## §1. 100% Test Coverage  \[stub\]

**Определение.** Everything must be covered by unit tests. Uncovered code is a risk.

**Origin.** TDD movement, Kent Beck, Uncle Bob, XP.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §2. Clean Architecture / N Layers of Abstraction  \[stub\]

**Определение.** Split code into layers (domain, application, infrastructure, presentation). Dependencies point inward.

**Origin.** Uncle Bob, «Clean Architecture». Previously Hexagonal/Onion Architecture.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §3. DRY (Don't Repeat Yourself) 🎯  \[filled\]

**Определение.** Never copy-paste. Any repetition is a candidate for abstraction.

**Origin.** «The Pragmatic Programmer», Hunt & Thomas, 1999.

**Условия провала.**

- When two similar things are merged into one abstraction and then diverge.
- Shared libraries between teams with different release cycles.
- Too early abstraction (before the 3rd real use case).

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Контр-догмы.**

- **WET (Write Everything Twice)** — _folk, anonymous_
  > Don't abstract until you've seen the repetition twice.
- **Rule of Three** — _Don Roberts via Martin Fowler, «Refactoring» (1999)_
  > Three repetitions — only then a candidate for abstraction.
- **The Wrong Abstraction** — _Sandi Metz, 2016_ ([source](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction))
  > Duplication is far cheaper than the wrong abstraction.
- **AHA (Avoid Hasty Abstractions)** — _Kent C. Dodds, 2019_ ([source](https://kentcdodds.com/blog/aha-programming))
  > Previously in the catalog AHA was incorrectly attributed to Sandi Metz — these are different authors.

**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- Knowledge repeats (business rule, formula, invariant), not code form.
- You see the third repetition (Rule of Three), and all three are called from the same context / same team / same release cycle.
- Cost of a wrong abstraction is lower than cost of duplication.

_Ломай догму, когда:_

- Two code pieces look the same but change for different reasons (different stakeholders, different release cycles, different domains).
- The abstraction crosses team or service boundaries.
- There are only 1–2 repetitions and you haven't seen how it actually changes yet.
- Code is exploratory / throwaway.

**Main signal:** Every new requirement adds an if-flag to the 'shared' function. That's not extension — that's admission you glued two different things together.

**Related tags:** `wrong-abstraction`.

## §4. Microservices for Everything 🎯  \[filled\]

**Определение.** Monolith is evil. Cut the system into small services.

**Origin.** Netflix, Amazon, ThoughtWorks, ~2014.

**Условия провала.**

- Team < 10 people.
- One product, not independent business units.
- Distributed transactions become the norm.
- Debug takes 3 hours because traces scatter across 12 services.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- Netflix, Amazon (at a certain scale) — Need specific post-mortem links with numbers.

**Контр-догмы.**

- **MonolithFirst** — _Martin Fowler, 2015_ ([source](https://martinfowler.com/bliki/MonolithFirst.html))
  > Almost all successful microservice systems started as monoliths and were split later.
- **Modular Monolith** — _Shopify and others_
  > Modules with clear boundaries inside one process. No network boundaries, but with the ability to split later.
- **Prime Video monolith migration** — _Amazon Prime Video Tech Blog, 2023_ ([source](https://www.primevideotech.com/video-streaming/scaling-up-the-prime-video-audio-video-monitoring-service-and-reducing-costs-by-90))
  > Moving from serverless/microservices back to monolith with 90% reduction in infrastructure costs.

**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- You genuinely have multiple independent business domains with different teams, release cycles, and scale.
- Team is larger than 10–15 people and there's concrete pain from the monolith already.
- You're willing to pay the operational cost of a distributed system.

_Ломай догму, когда:_

- Team < 10 people and/or one product.
- Project is in startup / MVP phase — domain hasn't stabilized yet.
- Distributed transactions or debug sessions appear where traces scatter across 5+ services.
- The main pain is in business logic complexity, not scale.

**Main signal:** Distributed monolith — a bunch of small services that still change together and deploy together, but now over the network.


## §5. OOP as the Only Truth (inheritance everywhere)  \[stub\]

**Определение.** Everything is an object. Inheritance is the primary tool for reuse.

**Origin.** Smalltalk, Java, GoF Design Patterns.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

**Related tags:** `deep-inheritance`.

## §6. TDD (Test-Driven Development) 🎯  \[filled\]

**Определение.** Red-Green-Refactor. Write the test first, then the code.

**Origin.** Kent Beck.

**Условия провала.**

- Unknown domain — you don't yet know what the API should look like.
- UI code, visualizations.
- Research / exploratory coding.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Контр-догмы.**

- **Spike First** — _Kent Beck, «Extreme Programming Explained» (1999)_
  > In an unknown domain, first a spike (throwaway prototype without tests), then discard it, then rewrite with TDD.
- **Test After / Test Last** — _folk, counter-practice_
  > Tests are written after implementation, when the API has stabilized. Domain: UI, exploratory, research.
- **Characterization Testing** — _Michael Feathers, «Working Effectively with Legacy Code» (2004)_
  > For legacy without tests: test locks in current behavior so you can refactor safely.
- **TDD is dead. Long live testing.** — _DHH (David Heinemeier Hansson), 2014_ ([source](https://dhh.dk/2014/tdd-is-dead-long-live-testing.html))
  > TDD as ideology led to over-mocking and designing for tests instead of designing for the problem.

**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- You already understand the domain and roughly know what the API should look like.
- Working on stable business logic you plan to refactor.
- Cost of a production error is very high (finance, security, medicine, billing).

_Ломай догму, когда:_

- You're in an unknown domain — use Spike First.
- Working with UI, complex visual states, or external integrations — Test After.
- Working with legacy without tests — Characterization Testing.
- Prototype / proof of concept that will be thrown away in a week.

**Main signal:** You write a test before you understood what the code should do. Result — well-tested wrong design + a forest of mocks.


## §7. SOLID as Law  \[stub\]

**Определение.** SRP, OCP, LSP, ISP, DIP — five principles all code must follow.

**Origin.** Uncle Bob, 2000s.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §8. Self-documenting code (no comments needed)  \[stub\]

**Определение.** Good code reads without comments. Comments are a sign of unclear code.

**Origin.** Uncle Bob, «Clean Code».

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §9. Premature optimization is the root of all evil  \[stub\]

**Определение.** Don't optimize until you've profiled. (Usually cited without context.)

**Origin.** Donald Knuth, 1974. Full quote: «We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil. Yet we should not pass up our opportunities in that critical 3%.»

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §10. Functional purity / Immutability everywhere  \[stub\]

**Определение.** Avoid mutations. Pure functions. No side effects.

**Origin.** Haskell community, FP renaissance of the 2010s, React/Redux.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §11. KISS (Keep It Simple, Stupid)  \[draft\]

**Определение.** Prefer simple solutions over complex ones. Complexity is the enemy. Remove everything that isn't strictly necessary.


**Origin.** U.S. Navy, 1960. Kelly Johnson (Lockheed Skunk Works) insisted aircraft be repairable in combat with basic tools. Software adoption via Unix philosophy («Do one thing well») and later «Clean Code» culture.


**Условия провала.**

- KISS used as a reason to avoid thinking deeply about the problem.
- Simplicity of implementation confused with simplicity of the model.
- Removing real complexity that the domain actually has — just hiding it elsewhere.
- Team conflates 'familiar' with 'simple'.
- 'Stupid' in the slogan is taken literally — optimizing for the dumbest solution, not the clearest one.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Контр-догмы.**

- **Simple but Smart = Genius** — _Yegor Gaidar, 2026 (ArchDogma issue ARC-222)_
  > KISS without intelligence produces dumb simplicity. Real mastery is achieving simple interfaces over genuinely complex systems — not pretending complexity doesn't exist. Minecraft: one voxel, infinite depth. Einstein: «Everything should be made as simple as possible, but not simpler.»

- **Simple Made Easy** — _Rich Hickey, Strange Loop 2011_ ([source](https://www.infoq.com/presentations/Simple-Made-Easy/))
  > «Simple» (few interleaved concerns) ≠ «easy» (familiar/convenient). Easy solutions can be complected. The goal is simplicity of the model, not ease of the implementation.

- **Worse Is Better** — _Richard Gabriel, 1989_ ([source](https://www.dreamsongs.com/WIB.html))
  > The «New Jersey style» — simple implementation, imperfect interface — often wins in practice over the «MIT style» correct-interface design. A warning that KISS can be weaponized to ship deliberately incomplete things.


**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- Two designs solve the same problem — pick the one with fewer moving parts.
- Complexity is coming from your design choices, not from the domain.
- You can remove something and the system still correctly handles all real cases.

_Ломай догму, когда:_

- The problem is genuinely complex — KISS doesn't simplify the problem, just hides it.
- You're simplifying the wrong layer (impl) while complicating the right one (API/model).
- The 'simple' solution requires callers to carry the complexity you refused to encode.
- You're optimizing for lines of code, not for conceptual clarity.

**Main signal:** Every new edge case requires a workaround in the calling code. Your 'simple' core is pushing complexity outward — that's not KISS, that's a tax on every consumer.



## Кандидаты

Антипаттерны и догмы-в-наблюдении. Не имеют §-номера; могут быть promoted в `dogmas` после накопления кейсов.

### God File / God Class  \[god-class\]

Anti-pattern consequence, not a dogma. Appears from fear of refactoring + no tests + deadlines.

**Источники.**

- [SQLite amalgamation — deliberate performance decision (~238k lines)](https://sqlite.org/amalgamation.html)
- [Knight Capital 2012 — $440M from dead code in legacy](https://www.sec.gov/litigation/admin/2013/34-70694.pdf)
- Michael Feathers, «Working Effectively with Legacy Code» (2004)

**Related tags:** `god-function`, `god-class`, `long-function`.

### Long Parameter List  \[long-parameter-list\]

Classic code smell — when a signature demands too much, it can usually be split into a parameter object, keyword-only namespace, or two different functions.

**Источники.**

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


---

## Контрибьюция

Источник правды — `catalog/dogmas.yaml`. Правки идут туда, этот
файл перегенерируется через `archdogma render-catalog`.
Если нашёл расхождение между YAML и .md — значит забыли перегенерировать.
Репортни баг, не правь `.md` руками.
