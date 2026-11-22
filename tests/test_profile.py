import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from urllib.error import HTTPError
from xml.etree import ElementTree

from profile_readme.calendar import fetch_calendar, parse_calendar, validate_calendar
from profile_readme.cards import language_rows
from profile_readme.data import collect
from profile_readme.github import GitHub, GitHubError
from profile_readme.model import month_window, read_json, validate_config, validate_snapshot
from profile_readme.render import build, publish, validate_svg

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 11, 21)
CALENDAR = {"start": "2025-11-16", "counts": [0] * 369 + [2, 1], "levels": "0" * 369 + "21"}


def calendar_html():
    from datetime import timedelta

    first = date.fromisoformat(CALENDAR["start"])
    cells = []
    for i, (count, level) in enumerate(zip(CALENDAR["counts"], CALENDAR["levels"])):
        day = (first + timedelta(days=i)).isoformat()
        label = "No contributions" if not count else f"{count} contribution{'s' if count != 1 else ''}"
        cells.append(
            f'<td class="ContributionCalendar-day" id="day-{i}" data-date="{day}" data-level="{level}"></td>'
            f'<tool-tip for="day-{i}">{label} on November 21st.</tool-tip>'
        )
    return (
        '<h2 id="js-contribution-activity-description">3 contributions in the last year</h2>'
        '<table class="ContributionCalendar-grid">' + "".join(cells) + "</table>"
    )


def repo(name, language="Java", owner="KayssonGabriel", *, fork=False, private=False):
    return {
        "name": name,
        "full_name": f"{owner}/{name}",
        "owner": {"login": owner},
        "private": private,
        "fork": fork,
        "language": language,
    }


def commit(repository, digit, stamp="2026-04-01T00:10:00+02:00", author="KayssonGabriel"):
    return {
        "repository": repository,
        "sha": digit * 40,
        "author": {"login": author},
        "commit": {"author": {"date": stamp, "email": "omit@example.org"}, "message": "omit"},
    }


class FixtureAPI:
    def __init__(self, repos, commits):
        self.repos = repos
        self.matches = commits

    def repositories(self, login):
        return iter(self.repos)

    def commits(self, login, start, end):
        return iter(self.matches)


class CollectionTests(unittest.TestCase):
    def test_month_window_rollover(self):
        months = month_window(DAY)
        self.assertEqual(len(months), 12)
        self.assertEqual((months[0], months[-1]), ("2025-12", "2026-11"))

    def test_public_counts_deduplication_and_categories(self):
        own = repo("Project")
        fork = repo("Fork", fork=True)
        profile = repo("KayssonGabriel")
        other = repo("ThirdParty", owner="someone")
        private = repo("Private", private=True)
        match = commit(own, "a")
        api = FixtureAPI(
            [own, own, fork, profile, other, private, repo("NoLanguage", None)],
            [match, match, commit(fork, "b"), commit(other, "c"), commit(private, "d"),
             commit(profile, "e"), commit(own, "f", author="someone"),
             commit(own, "1", stamp="2026-12-01T00:00:00Z")],
        )
        snapshot = collect(api, "KayssonGabriel", DAY)
        self.assertEqual(snapshot["repositories"], {"own": 2, "forks": 1})
        self.assertEqual(snapshot["languages"], {"Java": 1})
        self.assertEqual(snapshot["months"]["2026-04"], {"own": 1, "forks": 1, "third_party": 1})
        self.assertNotIn("omit", json.dumps(snapshot))
        validate_snapshot(snapshot, "KayssonGabriel")


class GitHubTests(unittest.TestCase):
    def test_repo_pagination_and_page_size(self):
        api = GitHub()
        calls = []

        def request(path, params):
            calls.append((path, params))
            return [{}] * (100 if params["page"] == 1 else 1)

        api.request = request
        self.assertEqual(len(list(api.repositories("Octocat"))), 101)
        self.assertEqual([params["page"] for _, params in calls], [1, 2])
        self.assertEqual(calls[0][1]["type"], "owner")

    def test_commit_search_refuses_incomplete_or_truncated_data(self):
        api = GitHub()
        for total, incomplete in [(1, True), (1001, False), (1, False)]:
            with self.subTest(total=total, incomplete=incomplete):
                api.request = lambda path, params: {
                    "total_count": total, "incomplete_results": incomplete, "items": []
                }
                with self.assertRaises(GitHubError):
                    list(api.commits("Octocat", date(2026, 1, 1), DAY))

    def test_rate_limit_message_excludes_response_and_token(self):
        def reject(request, *args, **kwargs):
            raise HTTPError(request.full_url, 403, "secret error", {"Retry-After": "120"}, None)

        api = GitHub(token="secret-token", opener=reject)
        with self.assertRaisesRegex(GitHubError, "120 s") as raised:
            api.request("/users/Octocat/repos", {})
        self.assertNotIn("secret", str(raised.exception))


class CalendarTests(unittest.TestCase):
    def test_reads_daily_counts_and_intensities_from_the_public_grid(self):
        self.assertEqual(parse_calendar(calendar_html()), CALENDAR)

    def test_rejects_unverifiable_calendar_html(self):
        html = calendar_html()
        for invalid in (
            html.replace("3 contributions in", "4 contributions in"),
            html.replace('data-date="2026-11-21"', 'data-date="2026-11-22"'),
            html.replace('<tool-tip for="day-370">', '<tool-tip for="unmatched">'),
            html.replace('data-level="2"', 'data-level="0"'),
        ):
            with self.assertRaises(ValueError):
                parse_calendar(invalid)

    def test_snapshot_rejects_non_public_payload_fields(self):
        with self.assertRaises(ValueError):
            validate_calendar({**CALENDAR, "repository": "unexpected"})

    def test_fetch_queries_the_public_view_without_authorization(self):
        from io import BytesIO

        def request(req, *, timeout):
            self.assertEqual(req.full_url, "https://github.com/users/KayssonGabriel/contributions")
            self.assertNotIn("Authorization", dict(req.header_items()))
            return BytesIO(calendar_html().encode())

        self.assertEqual(fetch_calendar("KayssonGabriel", opener=request), CALENDAR)


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.config = read_json(ROOT / "config/profile.json")
        self.theme = read_json(ROOT / "config/theme.json")
        self.source = (ROOT / "profile_readme/readme.md.in").read_text(encoding="utf-8")
        self.snapshot = collect(FixtureAPI([], []), "KayssonGabriel", DAY)

    def build(self, *, static=False):
        return build(self.config, self.theme, self.source, self.snapshot, CALENDAR, static=static)

    def test_output_contract_and_static_mode(self):
        files = self.build()
        self.assertEqual(len(files), 17)
        self.assertIn("data/public.json", files)
        self.assertIn("assets/hero-flow-dark.svg", files["README.md"])
        self.assertIn("prefers-reduced-motion", files["assets/hero-flow-light.svg"])
        self.assertIn("3 contribuições", files["README.md"])
        static_files = self.build(static=True)
        self.assertNotIn("@keyframes", static_files["assets/hero-flow-light.svg"])
        for path, source in files.items():
            if path.endswith(".svg"):
                self.assertEqual(ElementTree.fromstring(source).tag, "{http://www.w3.org/2000/svg}svg")
                self.assertLess(len(source.encode()), 12_000)

    def test_xml_escaping_and_config_validation(self):
        self.config["name"] = 'Teste & <nome>'
        files = self.build()
        self.assertIn("Teste &amp; &lt;nome&gt;", files["assets/hero-flow-light.svg"])
        for slug in ("../unsafe", "hero", "hero-color", "hero-flow", "calendar-wave", "calendar-wave-loop", "ACTIVITY"):
            self.config["projects"][0]["slug"] = slug
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                validate_config(self.config, self.theme)

    def test_five_languages_are_listed_individually(self):
        counts = {"Java": 30, "C++": 10, "JavaScript": 5, "Python": 4, "PowerShell": 2}
        self.assertEqual(language_rows(counts)[-1], ("PowerShell", 2))

    def test_monthly_bars_and_table_use_all_contributions_in_the_calendar(self):
        calendar = {**CALENDAR, "counts": [7] + CALENDAR["counts"][1:], "levels": "3" + CALENDAR["levels"][1:]}
        files = build(self.config, self.theme, self.source, self.snapshot, calendar)
        readme = files["README.md"]
        activity = files["assets/activity-light.svg"]
        self.assertLess(readme.index("assets/calendar-wave-loop-light.svg"), readme.index("## Projetos em destaque"))
        self.assertLess(readme.index("## Projetos em destaque"), readme.index("assets/activity-light.svg"))
        self.assertIn("Contribuições por mês em texto", readme)
        self.assertNotIn("Commits por mês", readme)
        self.assertIn("10 contribuições", readme)
        self.assertIn("| nov/2025 | 7 |", readme)
        self.assertIn("| nov/2026 | 3 |", readme)
        root = ElementTree.fromstring(activity)
        ns = {"s": "http://www.w3.org/2000/svg"}
        self.assertIn("10 contribuições", root.find("s:desc", ns).text)
        self.assertEqual(len(root.findall('.//s:g[@class="bar"]', ns)), 2)

    def test_name_sweep_is_clipped_to_letterforms_and_has_a_static_mode(self):
        svg = "assets/hero-flow-light.svg"
        motion = self.build()[svg]
        static = self.build(static=True)[svg]
        ns = {"s": "http://www.w3.org/2000/svg"}
        root = ElementTree.fromstring(motion)
        mask = root.find(".//s:mask", ns)
        self.assertIsNotNone(mask)
        self.assertEqual(mask.find("s:text", ns).text, self.config["name"])
        group = root.find(f'.//s:g[@mask="url(#{mask.get("id")})"]', ns)
        self.assertEqual(group.find("s:rect", ns).get("opacity"), "0")
        self.assertIn("prefers-reduced-motion: no-preference", motion)
        self.assertIn("animation: name-sweep 7s linear infinite", motion)
        self.assertNotIn("<mask", static)
        still = ElementTree.fromstring(static)
        name = still.find('./s:text[@fill="url(#name-ink-gradient)"]', ns)
        self.assertEqual(name.text, self.config["name"])
        self.assertIsNotNone(still.find('.//s:linearGradient[@id="name-ink-gradient"]', ns))

    def test_circuit_signal_follows_the_visible_route_and_has_a_static_mode(self):
        files = self.build()
        static_files = self.build(static=True)
        asset = next(path for path in files if path.startswith("assets/hero-") and path.endswith("-dark.svg"))
        ns = {"s": "http://www.w3.org/2000/svg"}
        root = ElementTree.fromstring(files[asset])
        signal = root.find('./s:path[@class="circuit-signal"]', ns)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.get("opacity"), "0")
        route = signal.get("d")
        self.assertTrue(any(path.get("d") == route for path in root.findall("s:path", ns) if path is not signal))
        self.assertNotIn("circuit-signal", static_files[asset])

    def test_calendar_wave_preserves_the_grid_and_has_a_static_mode(self):
        files = self.build()
        static_files = self.build(static=True)
        asset = next(path for path in files if path.startswith("assets/calendar-") and path.endswith("-light.svg"))
        ns = {"s": "http://www.w3.org/2000/svg"}
        animated = ElementTree.fromstring(files[asset])
        still = ElementTree.fromstring(static_files[asset])
        grid = './s:g[@id="calendar-grid"]/s:path'
        self.assertEqual(
            [cell.attrib for cell in animated.findall(grid, ns)],
            [cell.attrib for cell in still.findall(grid, ns)],
        )
        self.assertGreater(len(still.findall(grid, ns)), 1)
        reference = animated.find('.//s:mask/s:use', ns)
        self.assertEqual(reference.get("href"), "#calendar-grid")
        self.assertIn("prefers-reduced-motion: no-preference", files[asset])
        self.assertIn("animation: calendar-wave 14s ease-out .18s infinite", files[asset])
        self.assertNotIn("calendar-wave", static_files[asset])

    def test_project_icon_animations_follow_project_type(self):
        files = self.build()
        still = self.build(static=True)
        keyframes = {"branch": "hub-entry", "tools": "terminal-cursor", "queue": "queue-step"}
        for project in self.config["projects"]:
            with self.subTest(project=project["slug"]):
                asset = f'assets/project-{project["slug"]}-dark.svg'
                self.assertIn(asset, files.keys())
                self.assertIn(asset, files["README.md"])
                self.assertIn(f'@keyframes {keyframes[project["icon"]]}', files[asset])
                self.assertIn("prefers-reduced-motion: no-preference", files[asset])
                self.assertNotIn("@keyframes", still[asset])
                self.assertIn(project["title"], still[asset])

    def test_language_motion_keeps_real_bar_lengths_and_numbers(self):
        self.snapshot["repositories"]["own"] = 5
        self.snapshot["languages"] = {"Java": 4, "PowerShell": 1}
        asset = "assets/languages-flow-light.svg"
        files = self.build()
        static_files = self.build(static=True)
        self.assertIn(asset, files.keys())
        animated = ElementTree.fromstring(files[asset])
        still = ElementTree.fromstring(static_files[asset])
        ns = {"s": "http://www.w3.org/2000/svg"}
        for shape in ("rect", "text"):
            self.assertEqual(
                [(item.attrib, item.text) for item in animated.findall(f"s:{shape}", ns)],
                [(item.attrib, item.text) for item in still.findall(f"s:{shape}", ns)],
            )
        glints = animated.findall('./s:g[@class="language-glints"]/s:rect', ns)
        self.assertEqual(len(glints), 2)
        self.assertTrue(all(glint.get("opacity") == "0" for glint in glints))
        self.assertNotIn("language-glints", static_files[asset])

    def test_svg_masks_and_gradients_can_only_reference_local_definitions(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg"><defs>'
            '<linearGradient id="sweep"><stop offset="1" stop-color="#123456"/></linearGradient>'
            '</defs><rect fill="url(#sweep)"/></svg>'
        )
        validate_svg(svg)
        for invalid in (
            svg.replace("url(#sweep)", "url(#missing)"),
            svg.replace('fill="url(#sweep)"', 'mask="url(#sweep)"'),
            svg.replace("url(#sweep)", "url(https://example.com/a.svg#sweep)"),
        ):
            with self.assertRaises(ValueError):
                validate_svg(invalid)

    def test_snapshot_rejects_invalid_months_private_fields_and_totals(self):
        self.snapshot["months"].pop("2026-03")
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, "KayssonGabriel")
        self.snapshot["months"]["2026-03"] = {"own": 0, "forks": 0, "third_party": 0}
        self.snapshot["languages"]["Java"] = 1
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, "KayssonGabriel")
        self.snapshot["languages"] = {}
        self.snapshot["email"] = "omit@example.org"
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, "KayssonGabriel")

    def test_validator_blocks_active_svg_content(self):
        for markup in ('<script/>', '<foreignObject/>', '<g onclick="bad"/>',
                       '<rect fill="url(https://bad.example/img)"/>',
                       '<use href="https://bad.example/img#grid"/>',
                       '<use href="#missing"/>',
                       '<style>@import "bad.css";</style>'):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                validate_svg(f'<svg xmlns="http://www.w3.org/2000/svg">{markup}</svg>')

    def test_publish_noop_and_freshness_check(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            files = self.build()
            self.assertEqual(len(publish(target, files)), 17)
            self.assertEqual(publish(target, files), [])
            first = target / "README.md"
            first.write_text("stale", encoding="utf-8")
            self.assertEqual(publish(target, files, check=True), ["README.md"])
            self.assertEqual(first.read_text(encoding="utf-8"), "stale")


if __name__ == "__main__":
    unittest.main()
