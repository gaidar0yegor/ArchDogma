"""YAML catalog → Markdown renderer (ADR-002).

`catalog/dogmas.yaml` is the source of truth. `DOGMAS.md` is derived from it
via `render_catalog(catalog) -> str`.

Goals:
- Deterministic output — same input, same bytes. Enables `render --check`.
- No creative prose. The renderer is a transform, not an author. If a field
  isn't in the YAML, the renderer writes a short honest placeholder
  (e.g., "нет кейсов пока — статус `stub`").
- UTF-8 / русский язык — explicit, no transliteration.

Not goals for alpha3:
- Jinja2 / template language. The YAML already is the template; a Python
  function is cheaper than an extra indirection.
- Localisation / multiple outputs. Single `.md` file, single language.
"""

from __future__ import annotations

from collections.abc import Iterable

from archdogma.catalog.loader import Catalog, CandidateRef, DogmaRef

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

AUTOGEN_BANNER = (
    "<!-- AUTO-GENERATED from catalog/dogmas.yaml — "
    "DO NOT EDIT BY HAND. Run: archdogma render-catalog -->\n"
)


def render_catalog(catalog: Catalog) -> str:
    """Render a loaded Catalog into a Markdown document.

    The returned string ends with exactly one trailing newline — so writing
    it verbatim produces POSIX-clean files.
    """
    lines: list[str] = [AUTOGEN_BANNER.rstrip("\n"), ""]
    lines.append("# Каталог догм")
    lines.append("")
    if catalog.updated:
        lines.append(f"_Обновлено: {catalog.updated} — schema v{catalog.schema_version}._")
        lines.append("")

    lines.extend(_render_preamble())
    lines.append("")

    # Dogmas in number order. ADR-002 pins numbers sequential from 1.
    for d in sorted(catalog.dogmas, key=lambda x: x.number):
        lines.extend(_render_dogma(d))
        lines.append("")

    if catalog.candidates:
        lines.append("## Кандидаты")
        lines.append("")
        lines.append(
            "Антипаттерны и догмы-в-наблюдении. Не имеют §-номера; могут быть "
            "promoted в `dogmas` после накопления кейсов."
        )
        lines.append("")
        for c in catalog.candidates:
            lines.extend(_render_candidate(c))
            lines.append("")

    lines.extend(_render_postamble())
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _render_preamble() -> list[str]:
    return [
        "Правила каталога:",
        "",
        "- Каждое утверждение имеет источник. Без источника — `honesty-bug`.",
        "- Каждая контр-догма имеет `attribution`. Без автора — тоже `honesty-bug`.",
        "- Догма, помеченная 🎯 v0.1-priority, обязана иметь статус не ниже `draft`.",
        "- Отсутствие тега ≠ отсутствие проблемы.",
    ]


def _render_postamble() -> list[str]:
    return [
        "---",
        "",
        "## Контрибьюция",
        "",
        "Источник правды — `catalog/dogmas.yaml`. Правки идут туда, этот",
        "файл перегенерируется через `archdogma render-catalog`.",
        "Если нашёл расхождение между YAML и .md — значит забыли перегенерировать.",
        "Репортни баг, не правь `.md` руками.",
    ]


def _render_dogma(d: DogmaRef) -> list[str]:
    marker = " 🎯" if d.v01_priority else ""
    header = f"## §{d.number}. {d.title}{marker}  \\[{d.status}\\]"
    lines = [header, ""]

    # Stub dogmas get a terse block — honest about not being filled.
    if d.status == "stub":
        defn = d.raw.get("definition")
        if defn:
            lines.append(f"**Определение.** {defn}")
            lines.append("")
        origin = d.raw.get("origin")
        if origin:
            lines.append(f"**Origin.** {origin}")
            lines.append("")
        lines.append("_Кейсы и honest verdict пока не заполнены (статус `stub`)._")
        if d.related_tags:
            lines.append("")
            lines.append(
                "**Related tags:** " + ", ".join(f"`{t}`" for t in d.related_tags) + "."
            )
        return lines

    # Filled / draft — full render.
    defn = d.raw.get("definition")
    if defn:
        lines.append(f"**Определение.** {defn}")
        lines.append("")

    origin = d.raw.get("origin")
    if origin:
        lines.append(f"**Origin.** {origin}")
        lines.append("")

    failure_conditions = d.raw.get("failure_conditions") or []
    if failure_conditions:
        lines.append("**Условия провала.**")
        lines.append("")
        for item in failure_conditions:
            lines.append(f"- {item}")
        lines.append("")

    lines.extend(_render_case_bucket("Failure cases", d.raw.get("failure_cases")))
    lines.extend(_render_case_bucket("Success cases", d.raw.get("success_cases")))

    counter_dogmas = d.raw.get("counter_dogmas") or []
    if counter_dogmas:
        lines.append("**Контр-догмы.**")
        lines.append("")
        for cd in counter_dogmas:
            lines.extend(_render_counter_dogma(cd))
        lines.append("")

    verdict = d.raw.get("honest_verdict")
    if verdict:
        lines.extend(_render_honest_verdict(verdict))

    if d.related_tags:
        lines.append(
            "**Related tags:** " + ", ".join(f"`{t}`" for t in d.related_tags) + "."
        )

    return lines


def _render_candidate(c: CandidateRef) -> list[str]:
    lines = [f"### {c.title}  \\[{c.id}\\]", ""]
    note = c.raw.get("note")
    if note:
        lines.append(note)
        lines.append("")

    sources = c.raw.get("sources") or []
    if sources:
        lines.append("**Источники.**")
        lines.append("")
        for s in sources:
            lines.append(_format_source(s))
        lines.append("")

    if c.related_tags:
        lines.append(
            "**Related tags:** " + ", ".join(f"`{t}`" for t in c.related_tags) + "."
        )
    return lines


# ---------------------------------------------------------------------------
# Sub-renderers
# ---------------------------------------------------------------------------


def _render_case_bucket(heading: str, value) -> list[str]:
    """Render failure_cases / success_cases.

    Value can be:
      - string marker (e.g. `need_postmortems`, `need_data`) — emitted verbatim.
      - list of dicts with title/source_url/summary — each a bullet.
      - None / empty — skipped.
    """
    if not value:
        return []
    out: list[str] = [f"**{heading}.**", ""]
    if isinstance(value, str):
        out.append(f"- _{value}_")
        out.append("")
        return out
    if isinstance(value, list):
        for item in value:
            out.append(_format_source(item))
        out.append("")
        return out
    # Unknown shape — stay honest, don't make things up.
    out.append(f"- _unsupported value shape for `{heading}`: {type(value).__name__}_")
    out.append("")
    return out


def _format_source(item) -> str:
    """Render one source entry as a single Markdown bullet."""
    if isinstance(item, str):
        return f"- {item}"
    if not isinstance(item, dict):
        return f"- {item!r}"
    title = item.get("title") or item.get("name") or "(untitled source)"
    url = item.get("url") or item.get("source_url")
    summary = item.get("summary") or item.get("thesis")
    if url:
        bullet = f"- [{title}]({url})"
    else:
        bullet = f"- {title}"
    if summary:
        bullet += f" — {summary}"
    return bullet


def _render_counter_dogma(cd: dict) -> list[str]:
    name = cd.get("name") or "(untitled)"
    attribution = cd.get("attribution") or "⚠ без attribution (honesty-bug)"
    thesis = cd.get("thesis")
    url = cd.get("source_url")
    head = f"- **{name}** — _{attribution}_"
    if url:
        head += f" ([source]({url}))"
    lines = [head]
    if thesis:
        lines.append(f"  > {thesis}")
    return lines


def _render_honest_verdict(v: dict) -> list[str]:
    status = v.get("status") or "pending"
    lines = [f"**Honest verdict** \\[{status}\\]."]
    lines.append("")

    follow = v.get("follow_when") or []
    if follow:
        lines.append("_Следуй догме, когда:_")
        lines.append("")
        for f in follow:
            lines.append(f"- {f}")
        lines.append("")

    brk = v.get("break_when") or []
    if brk:
        lines.append("_Ломай догму, когда:_")
        lines.append("")
        for b in brk:
            lines.append(f"- {b}")
        lines.append("")

    main = v.get("main_signal")
    if main:
        lines.append(f"**Main signal:** {main}")
        lines.append("")
    return lines


def _bullets(items: Iterable[str]) -> list[str]:
    """Tiny helper — one bullet per item. Unused above but kept for future."""
    return [f"- {item}" for item in items]
