"""SVG templates. All inputs passed into markup are validated or escaped."""

from html import escape

from .calendar import daily_activity
from .model import HEAT_COLORS

SANS = "system-ui, Segoe UI, Arial, sans-serif"
SERIF = "Georgia, Times New Roman, serif"
MONO = "Consolas, Liberation Mono, monospace"
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def number(value):
    return f"{value:,}".replace(",", ".")


def month_label(key):
    return MONTHS[int(key[5:]) - 1]


def calendar_wave(color):
    return [
        '<defs><linearGradient id="calendar-wave-ink">',
        f'<stop offset="0" stop-color="{color}" stop-opacity="0"/>',
        f'<stop offset=".5" stop-color="{color}"/>',
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>',
        '</linearGradient>',
        '<mask id="calendar-wave-cells" maskUnits="userSpaceOnUse" mask-type="alpha" '
        'x="40" y="121" width="650" height="81"><use href="#calendar-grid"/></mask></defs>',
        '<g mask="url(#calendar-wave-cells)">',
        '<rect class="calendar-wave" x="-130" y="121" width="130" height="81" '
        'fill="url(#calendar-wave-ink)" opacity="0"/>',
        '</g>',
    ]


def calendar_card(calendar, colors, *, static):
    days = list(daily_activity(calendar))
    total = number(sum(calendar["counts"]))
    range_text = period([days[0][0].strftime("%Y-%m"), days[-1][0].strftime("%Y-%m")])
    levels = [[] for _ in HEAT_COLORS]
    month_labels = []
    for index, (day, _, level) in enumerate(days):
        week, row = divmod(index, 7)
        x, y = 40 + week * 12, 121 + row * 12
        levels[level].append(f"M{x} {y}h9v9h-9z")
        if day.day == 1:
            month_labels.append(label(x + 4, 111, MONTHS[day.month - 1], 18, colors["muted"],
                                      font=MONO, anchor="middle"))
    squares = [
        f'<path d="{"".join(points)}" fill="{colors[key]}"/>'
        for key, points in zip(HEAT_COLORS, levels) if points
    ]
    body = [
        label(38, 53, "Último ano no GitHub", 38, colors["ink"], font=SERIF, weight=700),
        label(40, 83, range_text, 23, colors["muted"], font=MONO),
        label(679, 53, total, min(48, 225 // len(total)), colors["accent"], weight=700, anchor="end"),
        label(679, 83, "no período", 22, colors["muted"], anchor="end"),
        *month_labels,
        '<g id="calendar-grid">', *squares, '</g>',
        *([] if static else calendar_wave(colors["accent"])),
        label(40, 227, "Um quadrado por dia", 21, colors["muted"]),
        label(544, 227, "Menos", 19, colors["muted"], anchor="end"),
        *(rect(556 + index * 14, 215, 10, 10, colors[key], 1) for index, key in enumerate(HEAT_COLORS)),
        label(638, 227, "Mais", 19, colors["muted"]),
    ]
    motion = """
@media (prefers-reduced-motion: no-preference) {
  .calendar-wave { animation: calendar-wave 14s ease-out .18s infinite; }
  @keyframes calendar-wave {
    0% { transform: translateX(0px); opacity: .25; }
    12% { transform: translateX(830px); opacity: .25; }
    13%, 100% { transform: translateX(830px); opacity: 0; }
  }
}
"""
    return frame("Calendário de contribuições", f"Total de {total} no período de {range_text}.",
                 250, colors, body, motion="" if static else motion)


def period(months):
    first, last = min(months), max(months)
    return f"{month_label(first)}/{first[2:4]} a {month_label(last)}/{last[2:4]}"


def label(x, y, value, size, color, *, font=SANS, weight=400, anchor="start", spacing=0):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-family="{font}" '
        f'font-weight="{weight}" text-anchor="{anchor}" letter-spacing="{spacing}">'
        f"{escape(str(value))}</text>"
    )


def rect(x, y, width, height, fill, radius=0, stroke="none"):
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>'


def line(x1, y1, x2, y2, color):
    return f'<path d="M{x1} {y1}L{x2} {y2}" fill="none" stroke="{color}"/>'


def frame(title, description, height, colors, body, *, motion=""):
    style = f"<style>{motion}</style>\n" if motion else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" width="720" '
        f'height="{height}" role="img" aria-labelledby="title details">\n'
        f'<title id="title">{escape(title)}</title><desc id="details">{escape(description)}</desc>\n'
        f"{style}{rect(1, 1, 718, height - 2, colors['background'], 20, colors['line'])}\n"
        + "\n".join(body) + "\n</svg>\n"
    )


def name_sweep(name_mask, colors):
    return [
        "<defs>",
        '<linearGradient id="name-sweep-gradient">',
        f'<stop offset="0" stop-color="{colors["accent"]}" stop-opacity="0"/>',
        f'<stop offset=".25" stop-color="{colors["accent"]}"/>',
        f'<stop offset=".53" stop-color="{colors["signal"]}"/>',
        f'<stop offset=".78" stop-color="{colors["accent"]}"/>',
        f'<stop offset="1" stop-color="{colors["accent"]}" stop-opacity="0"/>',
        "</linearGradient>",
        '<mask id="name-letterforms" maskUnits="userSpaceOnUse" x="35" y="65" width="510" height="90">',
        name_mask,
        "</mask>",
        "</defs>",
        '<g mask="url(#name-letterforms)">',
        '<rect class="name-sweep" x="-155" y="65" width="155" height="90" '
        'fill="url(#name-sweep-gradient)" opacity="0"/>',
        "</g>",
    ]


def hero(config, c, *, static):
    route = "M551 160H576L604 132V100L631 73H672"
    pattern = [line(x, 45, x, 184, c["line"]) for x in range(538, 687, 24)]
    pattern += [line(528, y, 688, y, c["line"]) for y in range(52, 185, 24)]
    artwork = [
        rect(532, 28, 162, 164, c["surface"], 15),
        '<g opacity=".45">', *pattern, "</g>",
        f'<path d="M548 80H576L628 132H674M554 179H610L655 134V56" fill="none" stroke="{c["line"]}" stroke-width="2"/>',
        f'<path d="{route}" fill="none" stroke="{c["accent"]}" stroke-linecap="round" stroke-width="3"/>',
    ]
    if not static:
        artwork.append(
            f'<path class="circuit-signal" d="{route}" pathLength="100" fill="none" '
            f'stroke="{c["signal"]}" stroke-linecap="round" stroke-width="4.5" opacity="0"/>'
        )
    for x, y, radius, fill, stroke in (
        (551, 160, 5, c["background"], c["accent"]),
        (604, 132, 6, c["background"], c["accent"]),
        (672, 73, 5, c["signal"], c["signal"]),
    ):
        artwork.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    name_size = min(60, 900 // len(config["name"]))
    subtitle_size = min(31, 840 // len(config["headline"]))
    name_style = {"font": SERIF, "weight": 700, "spacing": -2}
    name_ink = [
        '<defs><linearGradient id="name-ink-gradient">',
        f'<stop offset=".62" stop-color="{c["ink"]}"/>',
        f'<stop offset="1" stop-color="{c["accent"]}"/>',
        "</linearGradient></defs>",
    ]
    name = label(43, 132, config["name"], name_size, "url(#name-ink-gradient)", **name_style)
    sweep = [] if static else name_sweep(
        label(43, 132, config["name"], name_size, "#FFFFFF", **name_style), c
    )
    body = [
        *artwork,
        f'<circle cx="49" cy="54" r="5" fill="{c["signal"]}"/>',
        label(65, 62, f"@{config['login']}", 23, c["accent"], font=MONO),
        *name_ink,
        name,
        *sweep,
        label(45, 174, config["headline"], subtitle_size, c["muted"]),
        line(43, 209, 693, 209, c["line"]),
        line(43, 209, 118, 209, c["accent"]),
    ]
    motion = """
@media (prefers-reduced-motion: no-preference) {
  .name-sweep { animation: name-sweep 7s linear infinite; }
  .circuit-signal { stroke-dasharray: 9 115; animation: circuit-flow 7s linear infinite; }
  @keyframes name-sweep {
    0%, 3% { transform: translateX(0px); opacity: 1; }
    34% { transform: translateX(700px); opacity: 1; }
    35%, 100% { transform: translateX(700px); opacity: 0; }
  }
  @keyframes circuit-flow {
    0%, 43% { stroke-dashoffset: 10; opacity: 0; }
    48%, 66% { opacity: 1; }
    73%, 100% { stroke-dashoffset: -100; opacity: 0; }
  }
}
"""
    return frame(config["name"], config["headline"], 233, c, body, motion="" if static else motion)


PROJECT_ICONS = {
    "tools": (
        "M11 13H45V39H11ZM17 20L22 26L17 32M27 32H39",
        [(11, 13), (45, 39)],
    ),
    "queue": (
        "M9 14H26M9 26H26M9 38H26M31 26H46M40 20L46 26L40 32",
        [(9, 14), (9, 26), (9, 38)],
    ),
    "branch": (
        "M12 38V14M12 26H27M27 26L43 13M27 26L43 39",
        [(12, 14), (12, 38), (43, 13), (43, 39)],
    ),
}

PROJECT_MOTIONS = {
    "branch": (
        (
            '<circle class="hub-entry" cx="12" cy="26" r="3.5" fill="{signal}" opacity="0"/>',
            '<circle class="hub-upper" cx="27" cy="26" r="3.5" fill="{signal}" opacity="0"/>',
            '<circle class="hub-lower" cx="27" cy="26" r="3.5" fill="{signal}" opacity="0"/>',
        ),
        """
  .hub-entry { animation: hub-entry 10s linear infinite; }
  .hub-upper { animation: hub-upper 10s linear infinite; }
  .hub-lower { animation: hub-lower 10s linear infinite; }
  @keyframes hub-entry {
    0%, 8% { transform: translateX(0); opacity: 0; }
    10% { opacity: 1; }
    18% { transform: translateX(15px); opacity: 1; }
    19%, 100% { transform: translateX(15px); opacity: 0; }
  }
  @keyframes hub-upper {
    0%, 17% { transform: translate(0, 0); opacity: 0; }
    18% { opacity: 1; }
    28% { transform: translate(16px, -13px); opacity: 1; }
    32%, 100% { transform: translate(16px, -13px); opacity: 0; }
  }
  @keyframes hub-lower {
    0%, 17% { transform: translate(0, 0); opacity: 0; }
    18% { opacity: 1; }
    28% { transform: translate(16px, 13px); opacity: 1; }
    32%, 100% { transform: translate(16px, 13px); opacity: 0; }
  }
""",
    ),
    "tools": (
        ('<rect class="terminal-cursor" x="27" y="29.5" width="5" height="5" rx="1.5" '
         'fill="{signal}" opacity="0"/>',),
        """
  .terminal-cursor { animation: terminal-cursor 10s ease-in-out infinite; }
  @keyframes terminal-cursor {
    0%, 32% { transform: translateX(0); opacity: 0; }
    35% { opacity: 1; }
    45% { transform: translateX(7px); opacity: 1; }
    50%, 100% { transform: translateX(7px); opacity: 0; }
  }
""",
    ),
    "queue": (
        ('<circle class="queue-step" cx="9" cy="14" r="4.5" fill="{accent}" opacity="0"/>',),
        """
  .queue-step { animation: queue-step 10s linear infinite; }
  @keyframes queue-step {
    0%, 52% { transform: translateY(0); opacity: 0; }
    55%, 57% { transform: translateY(0); opacity: 1; }
    62%, 64% { transform: translateY(12px); opacity: 1; }
    69%, 71% { transform: translateY(24px); opacity: 1; }
    76%, 100% { transform: translateY(24px); opacity: 0; }
  }
""",
    ),
}


def project_card(project, c, *, static):
    kind = project["icon"]
    path, dots = PROJECT_ICONS[kind]
    markers, keyframes = PROJECT_MOTIONS[kind]
    icon = [
        '<g transform="translate(48 46)">',
        f'<path d="{path}" fill="none" stroke="{c["accent"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
        *(f'<circle cx="{x}" cy="{y}" r="3" fill="{c["signal"]}"/>' for x, y in dots),
        *(marker.format(**c) for marker in markers if not static),
        "</g>",
    ]
    title_size = min(40, 940 // len(project["title"]))
    body = [
        rect(31, 32, 89, 80, c["surface"], 13, c["line"]),
        *icon,
        label(146, 42, project["category"], 22, c["accent"], font=MONO, weight=600),
        label(144, 84, project["title"], title_size, c["ink"], font=SERIF, weight=700),
        label(146, 117, project["technology"], 24, c["muted"]),
        '<g transform="translate(651 57)">',
        f'<path d="M0 25L25 0M10 0H25V15" stroke="{c["accent"]}" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        "</g>",
    ]
    motion = "" if static else f"@media (prefers-reduced-motion: no-preference) {{{keyframes}}}\n"
    return frame(project["title"], project["description"], 145, c, body, motion=motion)


def activity_card(months, c, *, static):
    totals = dict(sorted(months.items()))
    total = sum(totals.values())
    total_label = number(total)
    peak = max(totals.values())
    body = [
        label(38, 57, "Contribuições por mês", 38, c["ink"], font=SERIF, weight=700),
        label(40, 93, period(months), 25, c["muted"], font=MONO),
        label(679, 59, total_label, min(50, 230 // len(total_label)), c["accent"], weight=700, anchor="end"),
        label(679, 94, "no período", 25, c["muted"], anchor="end"),
        line(40, 116, 680, 116, c["line"]),
        *[line(40, y, 680, y, c["line"]) for y in (153, 196, 240)],
    ]
    for index, (key, value) in enumerate(totals.items()):
        x = 54 + round(index * 612 / (len(totals) - 1))
        if value:
            height = max(3, round(value * 89 / peak))
            color = c["signal"] if value == peak else c["accent"]
            value_label = number(value)
            body.extend([
                '<g class="bar">',
                rect(x - 12, 240 - height, 24, height, color, min(height / 2, 5)),
                "</g>",
                label(x, 231 - height, value_label, min(24, 72 // len(value_label)), c["ink"],
                      weight=600, anchor="middle"),
            ])
        else:
            body.append(rect(x - 10, 237, 20, 3, c["line"], 1))
        body.append(label(x, 272, month_label(key), 23, c["muted"], font=MONO, anchor="middle"))
    motion = """
@media (prefers-reduced-motion: no-preference) {
  .bar { transform-origin: center bottom; transform-box: fill-box; animation: grow .75s ease-out both; }
  @keyframes grow { from { transform: scaleY(.2); opacity: .45; } to { transform: scaleY(1); opacity: 1; } }
}
"""
    unit = "contribuição" if total == 1 else "contribuições"
    return frame("Contribuições por mês", f"{total_label} {unit} de {period(months)}.",
                 300, c, body, motion="" if static else motion)


def language_rows(counts):
    rows = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    if len(rows) <= 5:
        return rows
    return [*rows[:5], ("Demais", sum(value for _, value in rows[5:]))]


def language_card(counts, c, *, static):
    rows = language_rows(counts)
    body = [
        label(38, 57, "Linguagens dos projetos", 38, c["ink"], font=SERIF, weight=700),
        label(40, 93, "Principal linguagem por repositório", 26, c["muted"]),
        line(40, 116, 680, 116, c["line"]),
    ]
    glints = []
    if not rows:
        body.append(label(40, 165, "Nenhuma linguagem identificada", 26, c["muted"]))
        height = 197
    else:
        maximum = max(value for _, value in rows)
        for index, (name, value) in enumerate(rows):
            y = 145 + index * 43
            width = max(7, round(343 * value / maximum))
            short_name = name if len(name) < 18 else f"{name[:16]}…"
            body.extend([
                label(40, y + 15, short_name, min(25, 245 // len(short_name)), c["ink"], weight=600),
                rect(271, y - 3, 343, 16, c["accent_soft"], 8),
                rect(271, y - 3, width, 16, c["accent"], 8),
                label(679, y + 15, number(value), 26, c["accent"], font=MONO, weight=700, anchor="end"),
            ])
            if not static:
                glints.append(
                    f'<rect x="271" y="{y - 3}" width="{width}" height="16" rx="8" '
                    f'fill="{c["signal"]}" opacity="0"/>'
                )
        height = 164 + len(rows) * 43
    motion = ""
    if glints:
        body.extend(['<g class="language-glints">', *glints, '</g>'])
        delays = "\n".join(
            f"  .language-glints rect:nth-child({index + 1}) {{ animation-delay: {index * .12:.2f}s; }}"
            for index in range(1, len(glints))
        )
        motion = f"""
@media (prefers-reduced-motion: no-preference) {{
  .language-glints rect {{
    transform-box: fill-box;
    transform-origin: left center;
    animation: language-glint 12s ease-in-out infinite;
  }}
{delays}
  @keyframes language-glint {{
    0%, 27% {{ transform: scaleX(.08); opacity: 0; }}
    32% {{ opacity: .4; }}
    39% {{ transform: scaleX(1); opacity: .3; }}
    43%, 100% {{ transform: scaleX(1); opacity: 0; }}
  }}
}}
"""
    return frame("Linguagens dos projetos", "Contagem por linguagem principal dos repositórios próprios.",
                 height, c, body, motion=motion)
