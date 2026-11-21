"""Read the contribution counts visible on GitHub's signed-out profile."""

import re
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.request import Request, build_opener

from .github import GitHubError, NoRedirects
from .model import count, fields, validate_login

MAX_BYTES = 750_000
ENGLISH_COUNT = r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)"
DAY_LABEL = re.compile(rf"(No contributions|{ENGLISH_COUNT} contributions?) on .+\.")
YEAR_LABEL = re.compile(rf"({ENGLISH_COUNT}) contributions? in the last year")


def daily_activity(calendar):
    start = date.fromisoformat(calendar["start"])
    for index, (value, level) in enumerate(zip(calendar["counts"], calendar["levels"])):
        yield start + timedelta(days=index), value, int(level)


def validate_calendar(calendar):
    fields(calendar, ("start", "counts", "levels"), "calendário")
    start = date.fromisoformat(calendar["start"])
    counts, levels = calendar["counts"], calendar["levels"]
    if (start.isoformat() != calendar["start"] or start.weekday() != 6 or not isinstance(counts, list)
            or not 365 <= len(counts) <= 373 or not isinstance(levels, str)
            or len(counts) != len(levels) or not re.fullmatch(r"[0-4]+", levels)):
        raise ValueError("Formato do calendário público inválido.")
    if any((count(value) == 0) != (level == "0") for value, level in zip(counts, levels)):
        raise ValueError("Contagens e intensidades do calendário são inconsistentes.")


class CalendarHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells = {}
        self.labels = {}
        self.header = []
        self.target = None
        self.in_header = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "h2" and attributes.get("id") == "js-contribution-activity-description":
            self.in_header = True
        elif tag == "td" and "ContributionCalendar-day" in attributes.get("class", "").split():
            key = attributes.get("id")
            if not key or key in self.cells:
                raise ValueError("Identificador de dia ausente ou duplicado.")
            self.cells[key] = (attributes.get("data-date"), attributes.get("data-level"))
        elif tag == "tool-tip" and attributes.get("for") in self.cells:
            self.target = attributes["for"]
            if self.target in self.labels:
                raise ValueError("Rótulo de dia duplicado.")
            self.labels[self.target] = []

    def handle_data(self, data):
        if self.in_header:
            self.header.append(data)
        elif self.target:
            self.labels[self.target].append(data)

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_header = False
        elif tag == "tool-tip":
            self.target = None


def parse_calendar(html):
    reader = CalendarHTML()
    reader.feed(html)
    reader.close()
    heading = YEAR_LABEL.fullmatch(" ".join("".join(reader.header).split()))
    if not heading or reader.cells.keys() != reader.labels.keys() or not reader.cells:
        raise ValueError("Calendário público incompleto.")
    rows = []
    for key, (day, level) in reader.cells.items():
        if not day or level not in {"0", "1", "2", "3", "4"}:
            raise ValueError("Data ou intensidade inválida no calendário.")
        label = DAY_LABEL.fullmatch(" ".join("".join(reader.labels[key]).split()))
        if not label:
            raise ValueError("Contagem diária ausente no calendário.")
        value = 0 if label[1] == "No contributions" else int(label[1].split()[0].replace(",", ""))
        rows.append((date.fromisoformat(day), value, level))
    rows.sort()
    start = rows[0][0]
    if any(day != start + timedelta(days=index) for index, (day, _, _) in enumerate(rows)):
        raise ValueError("O calendário contém datas duplicadas ou dias ausentes.")
    calendar = {
        "start": start.isoformat(),
        "counts": [value for _, value, _ in rows],
        "levels": "".join(level for _, _, level in rows),
    }
    validate_calendar(calendar)
    if sum(calendar["counts"]) != int(heading[1].replace(",", "")):
        raise ValueError("A soma diária diverge do total exibido pelo GitHub.")
    return calendar


def fetch_calendar(login, *, opener=None):
    validate_login(login)
    request = Request(f"https://github.com/users/{login}/contributions", headers={
        "User-Agent": "public-profile-readme-generator",
        "Accept": "text/html",
        "Accept-Language": "en-US",
    })
    open_public = opener or build_opener(NoRedirects).open
    try:
        with open_public(request, timeout=20) as response:
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Resposta excedeu o limite.")
        return parse_calendar(body.decode("utf-8"))
    except (OSError, ValueError):
        raise GitHubError("Não foi possível validar o calendário público do GitHub.") from None
