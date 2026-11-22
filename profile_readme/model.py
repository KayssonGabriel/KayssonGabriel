"""Validation for local configuration and the public aggregate snapshot."""

import json
import re
from datetime import date


THEMES = ("light", "dark")
HERO_ASSET = "hero-flow"
CALENDAR_ASSET = "calendar-wave"
HEAT_COLORS = ("heat_empty", "heat_low", "heat_mid", "heat_high", "heat_peak")
COLORS = {"background", "surface", "ink", "muted", "line", "accent", "accent_soft", "signal", *HEAT_COLORS}
ICONS = {"tools", "queue", "branch"}
SCOPES = ("own", "forks", "third_party")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fields(value, keys, label):
    if not isinstance(value, dict) or value.keys() != set(keys):
        raise ValueError(f"Campos inválidos em {label}.")


def validate_login(login):
    if not isinstance(login, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}", login):
        raise ValueError("Login do GitHub inválido.")


def valid_repo(value):
    return isinstance(value, str) and value not in {".", ".."} and bool(
        re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value)
    )


def valid_text(value, limit):
    return (
        isinstance(value, str) and 0 < len(value) <= limit
        and value == value.strip() and value.isprintable()
    )


def validate_config(config, themes):
    fields(config, ("login", "name", "headline", "projects"), "perfil")
    validate_login(config["login"])
    if not valid_text(config["name"], 28) or not valid_text(config["headline"], 38):
        raise ValueError("Nome ou subtítulo inválido para o cabeçalho.")
    if not isinstance(config["projects"], list) or not 1 <= len(config["projects"]) <= 6:
        raise ValueError("Configure entre um e seis projetos em destaque.")
    used = {"hero", "hero-color", HERO_ASSET, "calendar", CALENDAR_ASSET,
            "activity", "languages", config["login"].lower()}
    for project in config["projects"]:
        fields(project, ("slug", "title", "category", "technology", "description", "icon"), "projeto")
        slug = project["slug"]
        if not valid_repo(slug) or slug.lower() in used:
            raise ValueError("Nome de repositório inválido ou repetido.")
        used.add(slug.lower())
        limits = {"title": 30, "category": 24, "technology": 30, "description": 180}
        if not all(valid_text(project[key], limit) for key, limit in limits.items()):
            raise ValueError("Texto de projeto inválido ou longo demais para o cartão.")
        if project["icon"] not in ICONS:
            raise ValueError("Ícone de projeto inválido.")
    fields(themes, THEMES, "paletas")
    for theme in THEMES:
        fields(themes[theme], COLORS, "cores")
        if any(not isinstance(color, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", color)
               for color in themes[theme].values()):
            raise ValueError("Use cores hexadecimais de seis dígitos.")


def month_window(today):
    current = today.year * 12 + today.month - 1
    return [f"{index // 12:04}-{index % 12 + 1:02}" for index in range(current - 11, current + 1)]


def count(value):
    if type(value) is not int or not 0 <= value <= 1_000_000:
        raise ValueError("Contagem pública inválida.")
    return value


def validate_snapshot(snapshot, login):
    fields(snapshot, ("version", "login", "repositories", "languages", "months"), "dados públicos")
    if snapshot["version"] != 1 or snapshot["login"] != login:
        raise ValueError("Versão ou conta divergente nos dados públicos.")
    repositories = snapshot["repositories"]
    fields(repositories, ("own", "forks"), "repositórios")
    own = count(repositories["own"])
    count(repositories["forks"])
    languages = snapshot["languages"]
    if not isinstance(languages, dict) or any(not valid_text(key, 64) for key in languages):
        raise ValueError("Lista de linguagens inválida.")
    if sum(map(count, languages.values())) > own or any(value == 0 for value in languages.values()):
        raise ValueError("Contagens de linguagens inconsistentes.")
    months = snapshot["months"]
    if not isinstance(months, dict) or len(months) != 12:
        raise ValueError("A janela de atividade deve conter 12 meses.")
    latest = date.fromisoformat(f"{max(months)}-01")
    if sorted(months) != month_window(latest):
        raise ValueError("A janela de atividade tem meses ausentes ou inválidos.")
    for daily in months.values():
        fields(daily, SCOPES, "atividade mensal")
        for value in daily.values():
            count(value)
