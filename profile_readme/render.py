"""Build and check the complete set of publishable assets."""

import json
import os
import re
import tempfile
from html import escape
from string import Template
from xml.etree import ElementTree

from .calendar import monthly_contributions, validate_calendar
from .cards import activity_card, calendar_card, hero, language_card, month_label, number, period, project_card
from .model import CALENDAR_ASSET, HERO_ASSET, THEMES, validate_config, validate_snapshot

SVG_NAMESPACE = "{http://www.w3.org/2000/svg}"
SVG_TAGS = {
    f"{SVG_NAMESPACE}{tag}" for tag in (
        "svg", "title", "desc", "style", "rect", "text", "path", "circle", "g",
        "defs", "mask", "linearGradient", "stop", "use",
    )
}
SVG_ATTRIBUTES = {
    "viewBox", "width", "height", "role", "aria-labelledby", "id", "x", "y", "rx",
    "cx", "cy", "r", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
    "d", "class", "font-size", "font-family", "font-weight", "text-anchor", "letter-spacing",
    "opacity", "transform", "mask", "maskUnits", "mask-type", "offset", "stop-color", "stop-opacity",
    "pathLength", "href",
}
LOCAL_RESOURCES = {"fill": f"{SVG_NAMESPACE}linearGradient", "mask": f"{SVG_NAMESPACE}mask"}


def validate_svg(markup):
    if len(markup.encode("utf-8")) >= 12_000 or re.search(r"<!|<\?", markup):
        raise ValueError("SVG excede o orçamento ou contém declarações externas.")
    root = ElementTree.fromstring(markup)
    if root.tag != f"{SVG_NAMESPACE}svg":
        raise ValueError("Raiz SVG inválida.")
    elements = list(root.iter())
    definitions = {element.attrib["id"]: element.tag for element in elements if "id" in element.attrib}
    for element in elements:
        if element.tag not in SVG_TAGS:
            raise ValueError("Elemento SVG fora da lista permitida.")
        for name, value in element.attrib.items():
            if name not in SVG_ATTRIBUTES or re.search(r"(?:https?|data|javascript):|\\", value, re.I):
                raise ValueError("Atributo ou recurso SVG fora da lista permitida.")
            if name == "href" and (
                element.tag != f"{SVG_NAMESPACE}use" or value != "#calendar-grid"
                or definitions.get("calendar-grid") != f"{SVG_NAMESPACE}g"
            ):
                raise ValueError("O SVG só pode referenciar a própria grade do calendário.")
            if re.search(r"url\s*\(", value, re.I):
                reference = re.fullmatch(r"url\(#([a-zA-Z][a-zA-Z0-9_-]*)\)", value)
                if not reference or name not in LOCAL_RESOURCES or definitions.get(reference[1]) != LOCAL_RESOURCES[name]:
                    raise ValueError("Use apenas referências SVG locais do tipo permitido.")
        if element.tag == f"{SVG_NAMESPACE}style" and re.search(
            r"@import|url\s*\(|(?:https?|data|javascript):|\\", element.text or "", re.I
        ):
            raise ValueError("Recurso CSS externo ou inválido.")


def picture(asset, alt):
    return (
        '<picture>\n'
        f'  <source media="(prefers-color-scheme: dark)" srcset="assets/{asset}-dark.svg">\n'
        f'  <img src="assets/{asset}-light.svg" width="720" alt="{escape(alt, quote=True)}">\n'
        '</picture>'
    )


def markdown_text(value):
    return re.sub(r"([\\\x60*_\[\]|~])", r"\\\1", escape(value))


def assemble_readme(template, config, snapshot, months):
    base_url = f"https://github.com/{config['login']}"
    projects = []
    for project in config["projects"]:
        alt = f"{project['title']} — {project['technology']}"
        art = picture(project["slug"], alt)
        projects.append(
            f'<a href="{base_url}/{project["slug"]}">\n{art}\n</a>\n\n'
            + markdown_text(project["description"])
        )

    repositories = snapshot["repositories"]
    n_own, n_forks = repositories["own"], repositories["forks"]
    language_summary = (
        f"**{number(n_own)} {'repositório próprio' if n_own == 1 else 'repositórios próprios'}** "
        f"· {number(n_forks)} {'fork público' if n_forks == 1 else 'forks públicos'}. "
        "Cada repositório próprio com linguagem identificada conta uma vez no gráfico."
    )
    language_table = [
        "| Linguagem | Repositórios |", "| --- | ---: |",
        *(f"| {markdown_text(name)} | {number(value)} |" for name, value in sorted(
            snapshot["languages"].items(), key=lambda item: (-item[1], item[0].casefold())
        )),
    ] if snapshot["languages"] else ["Nenhuma linguagem identificada."]
    total = sum(months.values())
    activity_table = [
        "| Mês | Contribuições |", "| --- | ---: |",
        *(f"| {month_label(key)}/{key[:4]} | {number(value)} |" for key, value in months.items()),
    ]
    unit = "contribuição" if total == 1 else "contribuições"
    return Template(template).substitute(
        hero=picture(HERO_ASSET, f"{config['name']} — {config['headline']}"),
        calendar=picture(CALENDAR_ASSET, "Calendário diário de contribuições no GitHub."),
        calendar_summary=(
            f"**{number(total)} {unit}** no calendário do GitHub ({period(months)}). "
            "A contagem inclui a atividade privada exibida anonimamente no perfil."
        ),
        projects="\n\n".join(projects),
        activity=picture("activity", f"Gráfico de contribuições por mês, de {period(months)}."),
        languages=picture("languages", "Gráfico das linguagens predominantes nos repositórios próprios."),
        language_summary=language_summary,
        activity_table="\n".join(activity_table),
        language_table="\n".join(language_table),
        repositories_url=f"{base_url}?tab=repositories",
    ).rstrip() + "\n"


def build(config, themes, template, snapshot, calendar, *, static=False):
    validate_config(config, themes)
    validate_snapshot(snapshot, config["login"])
    validate_calendar(calendar)
    months = monthly_contributions(calendar)
    files = {}
    for theme in THEMES:
        colors = themes[theme]
        cards = {
            HERO_ASSET: hero(config, colors, static=static),
            CALENDAR_ASSET: calendar_card(calendar, colors, static=static),
            "activity": activity_card(months, colors, static=static),
            "languages": language_card(snapshot["languages"], colors),
            **{project["slug"]: project_card(project, colors) for project in config["projects"]},
        }
        for name, markup in cards.items():
            validate_svg(markup)
            files[f"assets/{name}-{theme}.svg"] = markup
    files["data/public.json"] = json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    files["data/calendar.json"] = json.dumps(calendar, ensure_ascii=False, separators=(",", ":")) + "\n"
    files["README.md"] = assemble_readme(template, config, snapshot, months)
    return files


def publish(location, files, *, check=False):
    changed = []
    for relative, content in files.items():
        target = location / relative
        payload = content.encode("utf-8")
        if target.exists() and target.read_bytes() == payload:
            continue
        changed.append(relative)
        if check:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temporary = handle.name
                handle.write(payload)
            os.replace(temporary, target)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)
    return changed
