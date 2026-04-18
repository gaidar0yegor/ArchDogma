# ADR-002: Machine-readable каталог — единый YAML-источник, markdown генерируется

## Status

Accepted — 2026-04-18.

## Context

После v0.1.0-alpha1 Probe выводит `Catalog links: (none — Probe→Catalog wiring ships with ADR-002)`. Это честная заглушка, но дальше без неё не проехать.

Три технических требования накапливаются одновременно:

1. **Probe → Catalog wiring.** Будущие Tier 1 детекторы должны уметь сказать не просто `[deep-nesting]`, а `[deep-nesting] → §3 DRY, §8 Self-documenting`. Grep по markdown — наивный, хрупкий, медленный и не переживёт переименования заголовков.
2. **Рост каталога.** В v0.1 — 16 догм (3 заполнены, 13 заготовки) + список кандидатов. Ожидаем рост до 25–30 в течение полугода. Ручной индекс «название → номер → теги» неподдерживаем.
3. **Валидация правил каталога.** У нас уже есть четыре правила (каждое утверждение с источником, никаких выдуманных цифр, etc.). Без схемы эти правила держатся на словах. Машина должна их проверять, иначе `honesty-bug` становится рекурсивным.

Рассматривались три варианта формата (обсуждение 2026-04-18):

1. YAML frontmatter внутри `DOGMAS.md`.
2. Отдельный `catalog/dogmas.yaml` + рукописный `DOGMAS.md`.
3. Единый YAML-источник, `DOGMAS.md` генерируется.

## Decision

Вариант **(3): единый YAML, markdown — сгенерированный артефакт.**

- `catalog/dogmas.yaml` — **единственный источник правды** для каталога.
- `DOGMAS.md` — генерируемый файл. Первая строка: `<!-- AUTO-GENERATED from catalog/dogmas.yaml — DO NOT EDIT BY HAND. Run: archdogma catalog render -->`.
- Правки идут в YAML, `DOGMAS.md` перегенерируется перед коммитом. PR, меняющий `DOGMAS.md` вручную, падает на CI.

### Schema v1

```yaml
schema_version: 1
updated: 2026-04-18

preamble: |
  <статический вступительный текст — рамка, правила, формат>

postamble: |
  <секция «Как контрибьютить»>

dogmas:
  - id: dry                      # slug, стабильный между версиями
    number: 3                    # порядковый номер в каталоге
    title: "DRY (Don't Repeat Yourself)"
    v01_priority: true           # 🎯 маркер в выводе
    status: filled               # stub | draft | filled

    definition: "Никогда не копипасть. Любое повторение — кандидат на абстракцию."
    origin: "«The Pragmatic Programmer», Hunt & Thomas, 1999."

    failure_conditions:
      - "Когда две похожие вещи объединяются в одну абстракцию, а потом расходятся."
      - "Shared libraries между командами с разными release-циклами."
      - "Слишком ранняя абстракция (до 3-го реального use case)."

    failure_cases: need_postmortems    # или список {title, source_url, summary}
    success_cases: need_data

    counter_dogmas:
      - name: "WET"
        attribution: "folk, анонимный"
        thesis: "Пока не увидел повторение дважды — не абстрагируй."
      - name: "Rule of Three"
        attribution: "Don Roberts via Martin Fowler, «Refactoring» (1999)"
        thesis: "Три повторения — только тогда кандидат на абстракцию."
      - name: "The Wrong Abstraction"
        attribution: "Sandi Metz, 2016"
        source_url: "https://sandimetz.com/blog/2016/1/20/the-wrong-abstraction"
        thesis: "Duplication is far cheaper than the wrong abstraction."
      - name: "AHA (Avoid Hasty Abstractions)"
        attribution: "Kent C. Dodds, 2019"
        source_url: "https://kentcdodds.com/blog/aha-programming"

    honest_verdict:
      status: draft_awaiting_cases    # draft_awaiting_cases | final | pending
      follow_when:
        - "Повторяется знание (бизнес-правило, формула), а не форма кода."
        - "Ты видишь третье повторение (Rule of Three)…"
      break_when:
        - "Два куска кода выглядят одинаково, но меняются по разным причинам."
        - "Абстракция пересекает границу команд или сервисов."
      main_signal: "Каждое новое требование добавляет в «общую» функцию if-флаг."

    related_tags:                  # AST теги, которые мэппятся на эту догму
      - wrong-abstraction          # будущий Tier 1/5

candidates:
  - title: "God File / God Class"
    note: "Антипаттерн-следствие, не догма."
    sources:
      - title: "SQLite amalgamation (осознанное решение ради производительности)"
        url: "https://sqlite.org/amalgamation.html"
      - title: "Knight Capital 2012 — $440M от dead code в legacy"
        url: "https://www.sec.gov/litigation/admin/2013/34-70694.pdf"
      - title: "Michael Feathers, «Working Effectively with Legacy Code» (2004)"
        url: null
```

Обязательные поля: `id`, `number`, `title`, `status`, `definition`. Всё остальное — опциональное с явными дефолтами.

### Правила, которые будет проверять валидатор

Правила — прямой перенос правил каталога из `DOGMAS.md` в машинный вид:

- Каждая `counter_dogma` обязана иметь `attribution`. Без автора → `honesty-bug`.
- Любая «реальная» ссылка на кейс должна быть либо валидным URL, либо строкой-маркером `need_postmortems` / `need_data`.
- `id` уникален в каталоге.
- `number` уникален и непрерывен в последовательности (1, 2, 3, …).
- Если `v01_priority: true`, то `status` не может быть `stub` (приоритетные догмы обязаны быть хотя бы `draft`).
- `honest_verdict.status: final` требует непустых `follow_when`, `break_when`, `main_signal`.

### Инструментарий

- `archdogma catalog render` — YAML → `DOGMAS.md`.
- `archdogma catalog validate` — проверка схемы и правил (офлайн; валидация URL — опционально через `--check-urls`).
- CI: `validate` + `render --check` (diff сгенерированного против коммита → fail при расхождении).

### Контракт для контрибьюторов

1. Правим `catalog/dogmas.yaml`.
2. Перед коммитом: `archdogma catalog render`.
3. Коммитим оба файла (`dogmas.yaml` + `DOGMAS.md`) как пару.
4. CI рефакторит всё равно — если забыл шаг 2, сборка красная.

## Consequences

### Positive

- **Один источник правды**. Дрейф между машинным и человеческим видом невозможен по дизайну.
- **Правила каталога становятся исполняемыми**. «Каждое утверждение с источником» — из этики в CI-чек.
- **Probe↔Catalog wiring** тривиален: tag → `related_tags` inverse lookup → список `Dogma` объектов.
- **Structured data бесплатно**. Будущие IDE-плагины, web-обёртки, отчёты получают готовый YAML без ре-парсинга markdown.
- **Атрибуция контр-догм формализована.** Нельзя написать "counter_dogma" без `attribution` — валидатор отклонит. Это соответствует существующему правилу каталога, теперь машинно.

### Negative

- **YAML — не markdown.** Редактирование многоабзацного honest_verdict в YAML менее приятно, чем в чистом md. Смягчение: block scalars (`|`), разбиение на `follow_when`/`break_when` списки (которые всё равно список буллетов в итоговом md).
- **Барьер для не-технических контрибьюторов.** Человек, который хочет прислать кейс, теперь упирается в YAML-синтаксис. Смягчение: issue template + готовый YAML-сниппет в CONTRIBUTING, мы сами переносим в файл.
- **Новая поверхность багов.** Renderer и validator — код, который может быть сломан. Баг в рендерере ломает сборку DOGMAS.md → ломает все PR. Смягчение: широкое тестовое покрытие рендерера + snapshot test (render(yaml) == expected.md).
- **`DOGMAS.md` в git дублирует YAML.** История git показывает оба файла — ревью .md-дифа и .yaml-дифа одновременно. Смягчение: в PR-template просим смотреть YAML, .md — для визуальной проверки форматирования.

### Neutral

- Статический текст (preamble, postamble) живёт внутри YAML как block scalars. Альтернатива — отдельный шаблон `dogmas.md.jinja2` — отложена до появления реальной потребности в templating-логике. Пока `preamble: |` достаточно.
- Ни YAML, ни markdown не лимитируют русский текст. `pyyaml.safe_dump(allow_unicode=True)` — явное требование в рендерере.

## Alternatives considered

### (1) YAML frontmatter в `DOGMAS.md` — rejected

```markdown
---
id: dry
number: 3
counter_dogmas: [...]
---
# 🎯 DRY ...
```

- Гибридный парсер (YAML + markdown в одном файле). Два источника парсер-багов на контрибуцию вместо одного.
- Frontmatter всё равно дублирует ключевые поля из основного текста (название, формулировку, кейсы) → та же проблема дрейфа, но в одном файле.
- Ограничение YAML-frontmatter в большинстве инструментов — один блок в начале файла. 16+ догм в одном документе не влезают органично.

### (2) Отдельный `catalog/dogmas.yaml` + рукописный `DOGMAS.md` — rejected

- **Два источника правды.** Дрейф — вопрос времени, не «если».
- CI-проверка «всё что в .md есть в .yaml» проверяет *присутствие*, а не *соответствие контента*. Можно синхронизировать индекс и рассинхронизировать текст — проверка не поймает.
- Удваивает когнитивную нагрузку на контрибьютора: «теперь правь оба».

## Migration plan

1. Перенести текущий `DOGMAS.md` в `catalog/dogmas.yaml` вручную (one-shot).
2. Реализовать `archdogma.catalog.loader.load_catalog()` (Pydantic или dataclass + manual validation — решим при имплементации).
3. Реализовать рендерер → `archdogma.catalog.renderer`.
4. Сгенерировать `DOGMAS.md` из YAML, сверить diff с текущей версией вручную, патчить YAML до полного совпадения.
5. Закоммитить пару `dogmas.yaml` + `DOGMAS.md` как первую пост-ADR-002 пару. Релиз: **v0.1.0-alpha2**.
6. Включить CI-чек на последующих PR.

Текущий `src/archdogma/catalog/loader.py` — явный stub с `NotImplementedError("see ADR-002 for planned format")`. После миграции он переписывается полностью.

## Known limitations schema v1

- **Отношения между догмами не моделируются.** «§3 DRY конфликтует с §7 SOLID при масштабе» — остаётся в прозе `honest_verdict`. Если появится реальная необходимость в графе отношений — schema v2.
- **URL-проверка офлайн по умолчанию.** Link-rot детект (`--check-urls`) — опция, в CI не включаем по умолчанию, чтобы внешняя недоступность сайта не ломала наши билды.
- **Локализация.** Каталог — русский. Поля `definition`, `origin` и т.д. — одноязычные. Перевод — не в v0.1 scope.
- **`related_tags`** — список имён тегов как строки. Сверка с реальным `TIER1_DETECTORS` — ответственность валидатора, не схемы.

## Expected next ADRs

- **ADR-003:** Trust Score — конкретные входящие сигналы и веса для Probe-вывода.
- **ADR-004:** Голосовой режим — TTS backend и форма output под screen readers.
- **ADR-005:** Cross-function / file-level детекторы (шаг вверх по лестнице README «Function → File → Module → Service»).
