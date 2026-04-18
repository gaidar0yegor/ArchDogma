# Changelog

Все значимые изменения фиксируются здесь. Формат основан на
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Семантика версий —
[SemVer](https://semver.org/lang/ru/), но на прe-альфе мажор/минор ещё не
застыли: ломающие изменения допускаются в любом выпуске до `0.1.0`.

## [Unreleased]

### Added
- **ADR-002 renderer + validator (долг закрыт)**.
  - `src/archdogma/catalog/renderer.py`: `render_catalog(cat) -> str`.
    Детерминистичен (bytes-identical runs), UTF-8, русский без
    транслитерации. Первая строка — AUTO-GENERATED banner.
    Stub-догмы получают честный placeholder вместо выдуманной прозы.
  - `src/archdogma/catalog/validator.py`: `validate_catalog(cat) ->
    list[ValidationIssue]`. Шесть правил из ADR-002:
    1. `counter_dogmas[].attribution` обязан быть (honesty-bug).
    2. `failure_cases` / `success_cases` — валидный marker
       (`need_postmortems` / `need_data` / `need_cases`) **или**
       список `{title, source_url, summary}`.
    3. `id` уникален по `dogmas + candidates`.
    4. `number` уникален **и** непрерывен от 1.
    5. `v01_priority: true` ⇒ `status != "stub"`.
    6. `honest_verdict.status: "final"` ⇒ непустые
       `follow_when` + `break_when` + `main_signal`.
  - CLI: `archdogma render-catalog [--output PATH] [--check]` —
    последний флаг для CI (diff против committed `.md`).
  - CLI: `archdogma validate-catalog` — exit 1 при любом error.
  - `DOGMAS.md` теперь сгенерирован из YAML (первая строка:
    AUTO-GENERATED banner). Правки идут в YAML.
  - `DogmaRef` / `CandidateRef` получили `raw: dict` (compare=False,
    repr=False) — рендерер и валидатор работают с полным YAML
    без раздувания типов.
- **ADR-002 wiring (gentle minimum)**: `catalog/dogmas.yaml` стал
  живым источником; `src/archdogma/catalog/loader.py` реализован —
  `DogmaRef`, `CandidateRef`, `Catalog` (frozen dataclasses), `tag_index`.
  Probe теперь принимает опциональный каталог и возвращает
  `ProbeResult.catalog_links: tuple[CatalogLink, ...]` с `tag_name →
  (entry_id, entry_kind, entry_title, entry_number)`.
  Рендерер YAML→Markdown и full-validator — всё ещё следующая веха.
- **CLI**: у `archdogma probe` появился флаг `--catalog PATH`
  (auto-detect по cwd, fallback — тёплое сообщение в stderr).
  `archdogma dogmas` теперь читает YAML (не режет heading-ы из `.md`);
  поддерживает `--include-stubs/--no-stubs` и
  `--include-candidates/--no-candidates`.
- **Tier 1 детектор `long-function`** — второй тег в реестре.
  - SLOC-метрика: множество физических строк, на которых живёт ≥1 AST-стейтмент.
    Blanks, comment-only lines, начальный docstring и тела вложенных
    `def`/`class` не считаются (те — отдельные скоупы).
  - Multi-line statement корректно засчитывается как N строк.
  - Дефолтный порог: 80. Конфигурируется параметром `threshold`.
  - Источник в детали тега: честно помечен как
    "no research-backed absolute threshold — 50/80/100 heuristics vary by style guide".
  - End-to-end фикстура `tests/fixtures/long_function_sample.py::long_and_deep`
    триггерит **оба** детектора (`deep-nesting` + `long-function`)
    на одном probe — регрессия для TIER1_DETECTORS как реестра.
- **Tier 1 детектор `god-function`** — третий тег в реестре.
  - AND-семантика двух порогов: `SLOC ≥ loc_threshold` **И**
    `branches ≥ branch_threshold`. Либо один — разные запахи, не этот.
  - Ветки McCabe-style: `if / elif / for / while / except / case`.
    `with` — последовательный, не ветка. Boolean `and/or` — не считаются.
  - Scope boundary: ветки вложенных `def` / `class` принадлежат им, не
    внешней функции (регрессия закрыта тестом).
  - Дефолты: 200 SLOC и 15 branches. Конфигурируется.
  - Honest source note: McCabe (1976) даёт счёт ветвей;
    «no research-backed absolute god-function threshold exists».
  - Фикстура `tests/fixtures/god_function_sample.py::dispatch_everything`
    (209 SLOC, 18 branches) — триггерит **оба** `long-function` и
    `god-function`, оба цепляют God Class candidate в каталоге.
- **File-level Probe** — методы классов и вложенные функции стали
  addressable (ранее только top-level `def`). Dotted qualified names:
  - `foo` — top-level
  - `MyClass.method` — метод класса
  - `outer.inner` — вложенная функция
  - `MyClass.method.inner` — вложенная внутри метода
  - `Outer.Inner.method` — метод вложенного класса
  - `list_all_functions(tree) -> list[DiscoveredFunction]` —
    depth-first source-order walk, возвращает `qualified_name`,
    `node`, `kind` (`function`/`method`/`nested`), `container`.
  - `find_function(tree, name)` теперь принимает dotted имя.
    Bare `regular_method` НЕ матчится на `Outer.regular_method` —
    partial match был бы сюрпризом и неоднозначным.
  - CLI: `archdogma probe FILE` без `--function` группирует вывод
    по kind (Top-level functions / Methods / Nested functions).
  - `--function Outer.method` резолвит корректно; в сообщении
    not-found перечисляются все addressable имена.
  - self/cls правило `too-many-params` теперь реально работает
    (ранее было future-proof заглушкой — Tier 1 видел только top-level).
- **Tier 1 детектор `too-many-params`** — четвёртый тег в реестре.
  - Считает `posonly + args + kwonly` параметры, плюс `*args` и `**kwargs`
    как +1 каждый. Leading `self` / `cls` исключается (future-proof
    для alpha4 class-method probe).
  - Defaulted args считаются наравне с required — defaults снижают
    шум вызова, но не сложность сигнатуры.
  - Дефолтный порог: 5. Конфигурируется параметром `threshold`.
  - Honest source note: Martin (≤3) / pylint R0913 (=5) / Sonar S107 (=7).
    "No research-backed absolute threshold exists".
  - Catalog candidate `long-parameter-list` добавлен со ссылками на
    Fowler "Refactoring" и Martin "Clean Code"; `too-many-params` →
    этот кандидат через `related_tags`.
  - Фикстура `tests/fixtures/too_many_params_sample.py`: `lean` (3, чисто),
    `on_the_line` (5, на пороге), `kitchen_sink` (7, с `*args`/`**kwargs`).
- **Авторство**: `pyproject.toml` и `LICENSE` обновлены —
  Yegor Gaidar, founder / author / executor.

### Dependencies
- `pyyaml >= 6.0` (каталог-лоадер).

### Tests
- +15 юнитов loader'а (`tests/test_catalog_loader.py`)
- +5 юнитов Probe↔Catalog wiring (`tests/test_probe_catalog_wiring.py`)
- +17 юнитов god-function (`tests/test_tier1_god_function.py`),
  +1 фикстура (`god_function_sample.py`).
- +14 юнитов рендерера (`tests/test_catalog_renderer.py`) —
  snapshot determinism, banner shape, section coverage,
  sync-guard против committed `DOGMAS.md`.
- +25 юнитов валидатора (`tests/test_catalog_validator.py`) —
  positive + negative для всех 6 правил.
- +26 юнитов too-many-params (`tests/test_tier1_too_many_params.py`) —
  threshold boundary, posonly/kwonly/vararg/kwarg shape, self/cls
  exclusion, async def, tag shape + honest sources.
- +23 юнита file-level probe (`tests/test_file_probe.py`) —
  list_all_functions shape, qualified-name resolution, nested
  classes/methods/defs, probe on method с self-exclusion,
  probe на classmethod с cls-exclusion, frozen DiscoveredFunction.
- Итого: **167/167 зелёных** (17 deep-nesting + 22 long-function +
  17 god-function + 26 too-many-params + 23 file-probe +
  15 catalog-loader + 14 catalog-renderer + 25 catalog-validator +
  5 probe-wiring + 3 smoke).

## [0.1.0-alpha1] — 2026-04-18

Первый работоспособный виток **Probe-петли** — AST → детектор → тег → CLI.
Не продукт, а proof-of-loop: доказываем, что архитектура Variant D
(Probe + Catalog) работает на живом Python-коде.

### Added
- **Function Probe**: анализ одной функции по имени из файла.
  - `archdogma probe FILE [--function NAME]` — парсит файл, находит
    функцию, прогоняет Tier 1 детекторы, печатает теги.
  - Без `--function` — перечисляет top-level функции файла.
- **Tier 1 детектор `deep-nesting`**.
  - Считает максимальную глубину вложенности управляющих конструкций
    (`if`, `for`, `while`, `with`, `try`, `match`).
  - Дефолтный порог: 4. Конфигурируется параметром `threshold`.
  - `elif` не стакается как вложенность (human-readable семантика).
  - Источник в детали тега: Cognitive Complexity (Sonarsource 2017) —
    честно помечен как "no research-backed absolute threshold exists".
- **CLI команда `archdogma dogmas`**: перечисляет заголовки из
  `DOGMAS.md`. Пропускает содержимое code fences (шаблоны не утекают).
- **Вывод**: `--plain` (по умолчанию, screen-reader friendly per
  [ADR-001](docs/adr/001-cli-first.md)) и `--pretty` (rich Panel + Table).
- **Каталог догм** `DOGMAS.md`: три v0.1 догмы заполнены с
  контр-догмами и honest verdicts —
  [§3 DRY](DOGMAS.md), [§4 Microservices](DOGMAS.md), [§6 TDD](DOGMAS.md).
  Правило: каждое утверждение имеет источник, иначе `honesty-bug`.
- **AST вокабуляр** `AST_TAGS_DRAFT.md`: пятитиерная классификация
  методов детекции; v0.1 лочится на Tier 1.
- **ADR-001**: выбор CLI-first, Python 3.11+, click + rich + pyttsx3.

### Notes (гарантии и ограничения)
- Tests: **17/17 unit + end-to-end на 4 фикстурах**.
- Probe работает только на top-level `def` / `async def`. Методы классов
  и вложенные функции пока не адресуются.
- Доктрина доступности: `--plain` — дефолт, не `--pretty`. Цвет не
  несёт информации. Никаких спиннеров и прогресс-баров.
- **Отсутствие тега ≠ отсутствие проблемы** — эта фраза печатается
  в пустом выводе намеренно.
- `Catalog links: (none)` — честная заглушка до ADR-002 (machine-readable
  catalog schema). Probe↔Catalog wiring — следующая веха.

### Known gaps
- Tier 1 детекторов всего один. Запланированы ещё пять (long-function,
  too-many-params, too-many-returns, broad-except, mutable-default-arg).
- §4 Microservices не детектируется на уровне функции — корректно,
  см. README-ladder «Function → File → Module → Service».
- §6 TDD чисто на AST не детектируется; Tier 4 (coverage data) —
  будущая работа.

[Unreleased]: https://example.invalid/archdogma/compare/v0.1.0-alpha1...HEAD
[0.1.0-alpha1]: https://example.invalid/archdogma/releases/tag/v0.1.0-alpha1
