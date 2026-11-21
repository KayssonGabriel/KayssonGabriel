"""Small, read-only client for the public endpoints used by the profile."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .model import validate_login


class GitHubError(RuntimeError):
    """An API failure that is safe to report without printing remote data."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token=None, *, opener=None):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "public-profile-readme-generator",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"
        self.open = opener or build_opener(NoRedirects).open

    def request(self, path, params):
        request = Request(
            f"https://api.github.com{path}?{urlencode(params)}", headers=self.headers
        )
        try:
            with self.open(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            retry = error.headers.get("Retry-After", "")
            limited = error.code in (403, 429) and (
                retry or error.code == 429 or error.headers.get("X-RateLimit-Remaining") == "0"
            )
            error.close()
            if limited:
                hint = f" após {retry} s" if retry.isascii() and retry.isdecimal() else " mais tarde"
                raise GitHubError(f"Limite da API. Tente novamente{hint}.") from None
            raise GitHubError(f"A API do GitHub retornou HTTP {error.code}.") from None
        except (URLError, TimeoutError, ValueError, OSError):
            raise GitHubError("Falha de rede ou resposta inválida da API do GitHub.") from None

    def repositories(self, login):
        validate_login(login)
        path = f"/users/{quote(login, safe='')}/repos"
        for page in range(1, 101):
            items = self.request(path, {
                "type": "owner", "sort": "full_name", "direction": "asc", "per_page": 100, "page": page,
            })
            if not isinstance(items, list):
                raise GitHubError("Lista de repositórios inválida.")
            yield from items
            if len(items) < 100:
                return
        raise GitHubError("Paginação de repositórios atingiu o limite de segurança.")

    def commits(self, login, start, end):
        validate_login(login)
        query = f"author:{login} is:public author-date:{start.isoformat()}..{end.isoformat()}"
        received = 0
        expected = None
        for page in range(1, 11):
            result = self.request("/search/commits", {
                "q": query, "sort": "author-date", "order": "desc", "per_page": 100, "page": page,
            })
            if not isinstance(result, dict) or result.get("incomplete_results") is not False:
                raise GitHubError("A busca de commits retornou resultados incompletos.")
            total = result.get("total_count")
            items = result.get("items")
            if type(total) is not int or not 0 <= total <= 1000 or not isinstance(items, list):
                raise GitHubError("A busca de commits retornou dados inválidos ou mais de 1.000 itens.")
            if expected is None:
                expected = total
            if total != expected or len(items) != min(100, expected - received):
                raise GitHubError("A busca de commits mudou durante a paginação.")
            received += len(items)
            yield from items
            if received == expected:
                return
