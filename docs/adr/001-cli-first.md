# ADR-001: CLI-first architecture for v0.1

## Status

Accepted — 2026-04-18.

## Context

Нужно выбрать форму доставки v0.1 ArchDogma. Три кандидата рассматривались (см. обсуждение 2026-04-18): Python CLI, Web app, VSCode/IDE extension.

Ключевые критерии отбора:
- Accessibility с первого дня (требование манифеста в README).
- Голосовой режим локально, без сетевой зависимости.
- Один язык (Python уже выбран как язык AST-анализа).
- Минимум технологий и scope creep в v0.1.
- Минимальный time-to-first-probe.

## Decision

v0.1 ArchDogma реализуется как **Python CLI**.

**Стек:**
- Python `>=3.11` (stdlib `tomllib`, `ast` достаточно современный, pattern matching доступен)
- `click` — CLI framework
- `rich` — опциональный pretty-output, **выключаемый** через `--plain` (см. ниже)
- `pyttsx3` — cross-platform TTS; с fallback на субпроцесс к нативным `say` (macOS) / `espeak-ng` (Linux) / SAPI (Windows)
- `gitpython` — опционально, для Tier 3 тегов (`old-code`, `high-churn`)
- `pytest` + `ruff` + `mypy` — dev

**Build backend:** `hatchling`. **Layout:** `src/archdogma`.

**Инверсия дефолта вывода (принципиально):**
Обычный CLI-подход — rich-форматирование по умолчанию, `--plain` как fallback. Мы делаем **наоборот**: plain structured text по умолчанию (parseable screen reader'ом), rich-форматирование через `--pretty`. Это прямое следствие манифеста «accessibility — не фича».

## Consequences

### Positive

- Screen readers работают в терминале из коробки на Linux/macOS.
- Голос через локальный TTS без сетевой зависимости.
- Один язык — один CI, один тест-раннер, одна экосистема зависимостей.
- `pip install -e .` → `archdogma probe <file>` — работающая команда с первого коммита.
- CLI встраивается в pre-commit хуки, CI-пайплайны, IDE tasks без дополнительных оберток.
- Самый низкий time-to-first-probe из трёх вариантов.
- Web-UI поверх CLI-ядра остаётся возможным для v0.2+ без переписывания.

### Negative

- Windows TTS из `pyttsx3` слабее, чем native macOS `say` / Linux `espeak-ng`. Документируем как known limitation.
- Графическая визуализация AST отсутствует. Теги выводятся текстом (файл + строка + колонка + описание). Tree-визуализация в CLI возможна, но не IDE-уровень.
- Не встраивается в редактор — юзер переключает контекст между IDE и терминалом.
- Для не-developer юзеров CLI — барьер. В v0.1 это **явно out of scope**: ArchDogma v0.1 — tool для инженеров.

### Neutral

- IDE extension возможен в v0.2+ через subprocess к CLI (compromise, но работающий паттерн — так делают `ruff`, `mypy`, `pytest` integrations).
- Web UI возможен в v0.2+ как тонкая FastAPI-обёртка поверх CLI-ядра.

## Alternatives considered

### Web app — rejected для v0.1

- AST-анализ требует либо отдельный Python backend (двойной стек), либо tree-sitter WASM в браузере (усложнение).
- Screen reader совместимость в web — ручная работа под WCAG 2.1 AA, не freebie.
- Хостинг / деплой / HTTPS / логи — ops, которого в v0.1 быть не должно.
- Time-to-v0.1 удлиняется минимум на 3–4 недели.

### VSCode/IDE extension — rejected для v0.1

- TypeScript/JS стек рядом с Python = два языка, два CI, два тест-раннера.
- Market охватывается только VSCode — JetBrains/Neovim users остаются за бортом.
- Голос в IDE требует desktop-hack или external TTS bridge.
- Extension review process добавляет время релиза.
- Time-to-v0.1 удлиняется минимум на 3–4 недели.

Оба варианта остаются открытыми для v0.2+. CLI-ядро проектируется так, чтобы его можно было вызвать как subprocess из web или extension.

## Known limitations v0.1, принятые явно

- **Windows TTS качество** — ниже, чем на macOS/Linux. Документируем.
- **Нет graphical AST visualization.** Output — текст.
- **Нет machine-readable формата каталога.** `DOGMAS.md` пока только human-readable. Для связки Probe → Dogma нужен либо YAML frontmatter на каждую догму, либо отдельный `catalog/index.yaml`. Это следующий ADR.
- **Tier 5 тегов (семантика) не делаем** — см. `AST_TAGS_DRAFT.md`.

## Expected next ADRs

- **ADR-002:** Machine-readable формат каталога догм (frontmatter vs отдельный index).
- **ADR-003:** Trust Score формула — конкретные входящие сигналы и веса.
- **ADR-004:** Голосовой режим — точный TTS backend и shape output под screen readers.
