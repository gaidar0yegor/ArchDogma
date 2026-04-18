# Changelog

Все значимые изменения фиксируются здесь. Формат основан на
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Семантика версий —
[SemVer](https://semver.org/lang/ru/), но на прe-альфе мажор/минор ещё не
застыли: ломающие изменения допускаются в любом выпуске до `0.1.0`.

## [Unreleased]

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
