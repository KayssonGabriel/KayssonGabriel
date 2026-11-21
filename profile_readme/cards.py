"""SVG templates. All inputs passed into markup are validated or escaped."""

from html import escape

SANS = "system-ui, Segoe UI, Arial, sans-serif"
SERIF = "Georgia, Times New Roman, serif"
MONO = "Consolas, Liberation Mono, monospace"
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def number(value):
    return f"{value:,}".replace(",", ".")


def month_label(key):
    return MONTHS[int(key[5:]) - 1]


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
            f'<path class="trace" d="{route}" pathLength="100" fill="none" stroke="{c["signal"]}" '
            'stroke-linecap="round" stroke-width="4" opacity="0"/>'
        )
    for x, y, radius, fill, stroke in (
        (551, 160, 5, c["background"], c["accent"]),
        (604, 132, 6, c["background"], c["accent"]),
        (672, 73, 5, c["signal"], c["signal"]),
    ):
        artwork.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    name_size = min(60, 900 // len(config["name"]))
    subtitle_size = min(31, 840 // len(config["headline"]))
    body = [
        *artwork,
        f'<circle cx="49" cy="54" r="5" fill="{c["signal"]}"/>',
        label(65, 62, f"@{config['login']}", 23, c["accent"], font=MONO),
        label(43, 132, config["name"], name_size, c["ink"], font=SERIF, weight=700, spacing=-2),
        label(45, 174, config["headline"], subtitle_size, c["muted"]),
        line(43, 209, 693, 209, c["line"]),
        line(43, 209, 118, 209, c["accent"]),
    ]
    motion = """
@media (prefers-reduced-motion: no-preference) {
  .trace { stroke-dasharray: 22 100; animation: trace-in 1.8s ease-out both; }
  @keyframes trace-in {
    0% { stroke-dashoffset: 22; opacity: 0; }
    24% { opacity: .95; }
    72% { opacity: .95; }
    100% { stroke-dashoffset: -100; opacity: 0; }
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


def project_card(project, c):
    path, dots = PROJECT_ICONS[project["icon"]]
    icon = [
        '<g transform="translate(48 46)">',
        f'<path d="{path}" fill="none" stroke="{c["accent"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
        *(f'<circle cx="{x}" cy="{y}" r="3" fill="{c["signal"]}"/>' for x, y in dots),
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
    return frame(project["title"], project["description"], 145, c, body)


def activity_card(months, c, *, static):
    totals = {key: sum(values.values()) for key, values in sorted(months.items())}
    total = sum(totals.values())
    peak = max(totals.values())
    body = [
        label(38, 57, "Commits por mês", 38, c["ink"], font=SERIF, weight=700),
        label(40, 93, period(months), 25, c["muted"], font=MONO),
        label(679, 59, number(total), 50, c["accent"], weight=700, anchor="end"),
        label(679, 94, "no período", 25, c["muted"], anchor="end"),
        line(40, 116, 680, 116, c["line"]),
        *[line(40, y, 680, y, c["line"]) for y in (153, 196, 240)],
    ]
    for index, (key, value) in enumerate(totals.items()):
        x = 58 + index * 55
        if value:
            height = max(3, round(value * 89 / peak))
            color = c["signal"] if value == peak else c["accent"]
            body.extend([
                '<g class="bar">',
                rect(x - 12, 240 - height, 24, height, color, min(height / 2, 5)),
                "</g>",
                label(x, 231 - height, number(value), 24, c["ink"], weight=600, anchor="middle"),
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
    return frame("Commits públicos por mês", f"{number(total)} commits de {period(months)}.",
                 300, c, body, motion="" if static else motion)


def language_rows(counts):
    rows = sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold()))
    if len(rows) <= 5:
        return rows
    return [*rows[:5], ("Demais", sum(value for _, value in rows[5:]))]


def language_card(counts, c):
    rows = language_rows(counts)
    body = [
        label(38, 57, "Linguagens dos projetos", 38, c["ink"], font=SERIF, weight=700),
        label(40, 93, "Principal linguagem por repositório", 26, c["muted"]),
        line(40, 116, 680, 116, c["line"]),
    ]
    if not rows:
        body.append(label(40, 165, "Nenhuma linguagem identificada", 26, c["muted"]))
        height = 197
    else:
        maximum = max(value for _, value in rows)
        for index, (name, value) in enumerate(rows):
            y = 145 + index * 43
            short_name = name if len(name) < 18 else f"{name[:16]}…"
            body.extend([
                label(40, y + 15, short_name, min(25, 245 // len(short_name)), c["ink"], weight=600),
                rect(271, y - 3, 343, 16, c["accent_soft"], 8),
                rect(271, y - 3, max(7, round(343 * value / maximum)), 16, c["accent"], 8),
                label(679, y + 15, number(value), 26, c["accent"], font=MONO, weight=700, anchor="end"),
            ])
        height = 164 + len(rows) * 43
    return frame("Linguagens dos projetos", "Contagem por linguagem principal dos repositórios próprios.",
                 height, c, body)
