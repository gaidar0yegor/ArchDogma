<!-- AUTO-GENERATED from catalog/dogmas.yaml — DO NOT EDIT BY HAND. Run: archdogma render-catalog -->

# Каталог догм

_Обновлено: 2026-04-18 — schema v1._

Правила каталога:

- Каждое утверждение имеет источник. Без источника — `honesty-bug`.
- Каждая контр-догма имеет `attribution`. Без автора — тоже `honesty-bug`.
- Догма, помеченная 🎯 v0.1-priority, обязана иметь статус не ниже `draft`.
- Отсутствие тега ≠ отсутствие проблемы.

## §1. 100% Test Coverage  \[stub\]

**Определение.** Всё должно быть покрыто unit-тестами. Непокрытый код — это риск.

**Origin.** TDD-движение, Kent Beck, Uncle Bob, XP.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §2. Clean Architecture / N слоёв абстракции  \[stub\]

**Определение.** Разделяй код на слои (domain, application, infrastructure, presentation). Зависимости идут внутрь.

**Origin.** Uncle Bob, «Clean Architecture». Ранее Hexagonal/Onion Architecture.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §3. DRY (Don't Repeat Yourself) 🎯  \[filled\]

**Определение.** Никогда не копипасть. Любое повторение — кандидат на абстракцию.

**Origin.** «The Pragmatic Programmer», Hunt & Thomas, 1999.

**Условия провала.**

- Когда две похожие вещи объединяются в одну абстракцию, а потом расходятся.
- Shared libraries между командами с разными release-циклами.
- Слишком ранняя абстракция (до 3-го реального use case).

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Контр-догмы.**

- **WET (Write Everything Twice)** — _folk, анонимный_
  > Пока не увидел повторение дважды — не абстрагируй.
- **Rule of Three** — _Don Roberts via Martin Fowler, «Refactoring» (1999)_
  > Три повторения — только тогда кандидат на абстракцию.
- **The Wrong Abstraction** — _Sandi Metz, 2016_ ([source](https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction))
  > Duplication is far cheaper than the wrong abstraction.
- **AHA (Avoid Hasty Abstractions)** — _Kent C. Dodds, 2019_ ([source](https://kentcdodds.com/blog/aha-programming))
  > Раньше в каталоге AHA ошибочно атрибутировался Sandi Metz — это разные авторы.

**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- Повторяется знание (бизнес-правило, формула, инвариант), а не форма кода.
- Ты видишь третье повторение (Rule of Three), и все три вызываются из одного контекста / одной командой / одного релизного цикла.
- Цена ошибочной абстракции ниже цены дубля.

_Ломай догму, когда:_

- Два куска кода выглядят одинаково, но меняются по разным причинам (разные стейкхолдеры, разные релиз-циклы, разные домены).
- Абстракция пересекает границу команд или сервисов.
- Есть только 1–2 повторения, и ты ещё не видел, как оно реально меняется.
- Код — исследовательский / одноразовый.

**Main signal:** Каждое новое требование добавляет в «общую» функцию if-флаг. Это не расширение — это признание, что ты склеил две разные вещи.

**Related tags:** `wrong-abstraction`.

## §4. Microservices для всего 🎯  \[filled\]

**Определение.** Монолит — зло. Режь систему на маленькие сервисы.

**Origin.** Netflix, Amazon, ThoughtWorks, ~2014.

**Условия провала.**

- Команда < 10 человек.
- Один продукт, не независимые бизнес-юниты.
- Distributed transactions становятся нормой.
- Debug занимает 3 часа, потому что trace разлетается по 12 сервисам.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- Netflix, Amazon (на определённом масштабе) — Нужны конкретные ссылки на post-mortems с числами.

**Контр-догмы.**

- **MonolithFirst** — _Martin Fowler, 2015_ ([source](https://martinfowler.com/bliki/MonolithFirst.html))
  > Почти все успешные микросервисные системы начинались как монолиты и были распилены позже.
- **Modular Monolith** — _Shopify и другие_
  > Модули с чёткими границами внутри одного процесса. Без сетевых границ, но с возможностью разделить позже.
- **Prime Video monolith migration** — _Amazon Prime Video Tech Blog, 2023_ ([source](https://www.primevideotech.com/video-streaming/scaling-up-the-prime-video-audio-video-monitoring-service-and-reducing-costs-by-90))
  > Переход от serverless/микросервисов обратно к монолиту со снижением инфраструктурных затрат на 90%.

**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- У тебя действительно несколько независимых бизнес-доменов с разными командами, релизными циклами и масштабом.
- Команда больше 10–15 человек и уже есть конкретная боль от монолита.
- Ты готов платить операционную цену распределённой системы.

_Ломай догму, когда:_

- Команда < 10 человек и/или один продукт.
- Проект в фазе стартапа / MVP — домен ещё не устоялся.
- Появляются distributed transactions или debug-сессии, где trace разлетается по 5+ сервисам.
- Основная боль — в сложности бизнес-логики, а не в масштабе.

**Main signal:** Distributed monolith — куча мелких сервисов, которые всё равно меняются вместе и деплоятся вместе, но теперь ещё через сеть.


## §5. OOP как единственная истина (наследование везде)  \[stub\]

**Определение.** Всё — объект. Наследование — главный инструмент переиспользования.

**Origin.** Smalltalk, Java, GoF Design Patterns.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

**Related tags:** `deep-inheritance`.

## §6. TDD (Test-Driven Development) 🎯  \[filled\]

**Определение.** Red-Green-Refactor. Сначала пишем тест, потом код.

**Origin.** Kent Beck.

**Условия провала.**

- Неизвестная область — ещё не знаешь, каким должен быть API.
- UI-код, визуализации.
- Research / exploratory coding.

**Failure cases.**

- _need_postmortems_

**Success cases.**

- _need_data_

**Контр-догмы.**

- **Spike First** — _Kent Beck, «Extreme Programming Explained» (1999)_
  > В неизвестной области сначала spike (одноразовый прототип без тестов), потом выбрасывается, потом переписывается через TDD.
- **Test After / Test Last** — _folk, контр-практика_
  > Тесты пишутся после реализации, когда API уже устоялся. Область: UI, exploratory, research.
- **Characterization Testing** — _Michael Feathers, «Working Effectively with Legacy Code» (2004)_
  > Для legacy без тестов: тест фиксирует текущее поведение, чтобы рефакторить безопасно.
- **TDD is dead. Long live testing.** — _DHH (David Heinemeier Hansson), 2014_ ([source](https://dhh.dk/2014/tdd-is-dead-long-live-testing.html))
  > TDD как идеология привела к over-mocking и дизайну под тесты вместо дизайна под задачу.

**Honest verdict** \[draft_awaiting_cases\].

_Следуй догме, когда:_

- Ты уже понимаешь домен и примерно знаешь, каким должен быть API.
- Работаешь над стабильной бизнес-логикой, которую планируешь рефакторить.
- Цена ошибки в проде очень высокая (финансы, безопасность, медицина, биллинг).

_Ломай догму, когда:_

- Ты в неизвестной области — используй Spike First.
- Работаешь с UI, сложными визуальными состояниями или внешними интеграциями — Test After.
- Работаешь с legacy без тестов — Characterization Testing.
- Прототип / proof of concept, который будет выброшен через неделю.

**Main signal:** Ты пишешь тест раньше, чем понял, что код должен делать. Результат — хорошо протестированный неправильный дизайн + лес моков.


## §7. SOLID как закон  \[stub\]

**Определение.** SRP, OCP, LSP, ISP, DIP — пять принципов, которым должен следовать весь код.

**Origin.** Uncle Bob, 2000-е.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §8. Self-documenting code (комментарии не нужны)  \[stub\]

**Определение.** Хороший код читается без комментариев. Комментарии — признак непонятного кода.

**Origin.** Uncle Bob, «Clean Code».

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §9. Premature optimization is the root of all evil  \[stub\]

**Определение.** Не оптимизируй, пока не профилировал. (Обычно цитируется без контекста.)

**Origin.** Donald Knuth, 1974. Полная цитата: «We should forget about small efficiencies, say about 97% of the time: premature optimization is the root of all evil. Yet we should not pass up our opportunities in that critical 3%.»

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## §10. Functional purity / Immutability везде  \[stub\]

**Определение.** Избегай мутаций. Чистые функции. Никаких side effects.

**Origin.** Haskell-сообщество, FP-ренессанс 2010-х, React/Redux.

_Кейсы и honest verdict пока не заполнены (статус `stub`)._

## Кандидаты

Антипаттерны и догмы-в-наблюдении. Не имеют §-номера; могут быть promoted в `dogmas` после накопления кейсов.

### God File / God Class  \[god-class\]

Антипаттерн-следствие, не догма. Появляется от страха рефакторинга + отсутствия тестов + дедлайнов.

**Источники.**

- [SQLite amalgamation — осознанное решение ради производительности (~238k строк)](https://sqlite.org/amalgamation.html)
- [Knight Capital 2012 — $440M от dead code в legacy](https://www.sec.gov/litigation/admin/2013/34-70694.pdf)
- Michael Feathers, «Working Effectively with Legacy Code» (2004)

**Related tags:** `god-function`, `god-class`, `long-function`.

### YAGNI (You Aren't Gonna Need It)  \[yagni\]


### KISS (Keep It Simple, Stupid)  \[kiss\]


### Agile и его ритуалы  \[agile-rituals\]


### Конфигурация вместо кода  \[config-over-code\]


### Serverless для всего  \[serverless-everything\]


### GraphQL вместо REST  \[graphql-over-rest\]


### NoSQL вместо SQL  \[nosql-over-sql\]


### Event Sourcing  \[event-sourcing\]


### Domain-Driven Design как обязательная практика  \[ddd-mandatory\]


### Code reviews должны быть обязательными всегда  \[code-reviews-mandatory\]


### Feature flags вместо веток  \[feature-flags-over-branches\]


### Монорепо vs полирепо  \[monorepo-vs-polyrepo\]


### Pair programming всегда  \[pair-programming-always\]


---

## Контрибьюция

Источник правды — `catalog/dogmas.yaml`. Правки идут туда, этот
файл перегенерируется через `archdogma render-catalog`.
Если нашёл расхождение между YAML и .md — значит забыли перегенерировать.
Репортни баг, не правь `.md` руками.
