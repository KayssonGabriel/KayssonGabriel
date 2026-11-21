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
        self.assertIn("assets/hero-dark.svg", files["README.md"])
        self.assertIn("prefers-reduced-motion", files["assets/hero-light.svg"])
        self.assertIn("Nenhum commit", files["README.md"])
        static_files = self.build(static=True)
        self.assertNotIn("@keyframes", static_files["assets/hero-light.svg"])
        for path, source in files.items():
            if path.endswith(".svg"):
                self.assertEqual(ElementTree.fromstring(source).tag, "{http://www.w3.org/2000/svg}svg")
                self.assertLess(len(source.encode()), 12_000)

    def test_xml_escaping_and_config_validation(self):
        self.config["name"] = 'Teste & <nome>'
        files = self.build()
        self.assertIn("Teste &amp; &lt;nome&gt;", files["assets/hero-light.svg"])
        for slug in ("../unsafe", "hero", "ACTIVITY"):
            self.config["projects"][0]["slug"] = slug
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                validate_config(self.config, self.theme)

    def test_five_languages_are_listed_individually(self):
        counts = {"Java": 30, "C++": 10, "JavaScript": 5, "Python": 4, "PowerShell": 2}
        self.assertEqual(language_rows(counts)[-1], ("PowerShell", 2))

    def test_calendar_precedes_projects_and_commit_bars_follow_them(self):
        files = self.build()
        readme = files["README.md"]
        self.assertLess(readme.index("assets/calendar-light.svg"), readme.index("## Projetos em destaque"))
        self.assertLess(readme.index("## Projetos em destaque"), readme.index("assets/activity-light.svg"))
        self.assertIn("Commits por mês em texto", readme)
        self.assertIn("3 contribuições", readme)

    def test_name_sweep_is_clipped_to_letterforms_and_has_a_static_mode(self):
        svg = "assets/hero-light.svg"
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
        self.assertNotIn("<mask", static)
        self.assertIn(self.config["name"], static)

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
