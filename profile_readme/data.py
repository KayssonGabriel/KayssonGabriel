"""Aggregate only public repository counts and indexed commit counts."""

import re
from collections import Counter
from datetime import date, datetime

from .model import SCOPES, month_window, valid_repo, valid_text


def repository(data, *, expected_owner=None):
    if not isinstance(data, dict) or data.get("private") is not False or data.get("visibility", "public") != "public":
        return None
    owner = data.get("owner")
    name = data.get("name")
    if (not isinstance(owner, dict) or not valid_text(owner.get("login"), 39)
            or not valid_repo(name) or type(data.get("fork")) is not bool):
        raise ValueError("Metadados inválidos de repositório público.")
    login = owner["login"].lower()
    if expected_owner and login != expected_owner:
        return None
    return login, name.lower()


def collect(api, login, today):
    """Return the aggregate without descriptions, names of third parties or commit payloads."""
    owner = login.lower()
    profile_repo = (owner, owner)
    own = forks = 0
    languages = Counter()
    seen = set()
    for item in api.repositories(login):
        key = repository(item, expected_owner=owner)
        if key is None or key == profile_repo or key in seen:
            continue
        seen.add(key)
        if item["fork"]:
            forks += 1
        else:
            own += 1
            language = item.get("language")
            if language is not None:
                if not valid_text(language, 64):
                    raise ValueError("Linguagem inválida em repositório público.")
                languages[language] += 1

    months = {month: dict.fromkeys(SCOPES, 0) for month in month_window(today)}
    start = date.fromisoformat(f"{min(months)}-01")
    seen.clear()
    for item in api.commits(login, start, today):
        if not isinstance(item, dict):
            raise ValueError("Resultado inválido na busca de commits.")
        repo = item.get("repository")
        key = repository(repo)
        author = item.get("author")
        if (key is None or key == profile_repo or not isinstance(author, dict)
                or str(author.get("login", "")).lower() != owner):
            continue
        sha = item.get("sha")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Identificador inválido na busca de commits.")
        identity = (*key, sha)
        if identity in seen:
            continue
        seen.add(identity)
        stamp = datetime.fromisoformat(item["commit"]["author"]["date"]).date()
        if not start <= stamp <= today:
            continue
        scope = "third_party" if key[0] != owner else "forks" if repo["fork"] else "own"
        months[stamp.strftime("%Y-%m")][scope] += 1

    return {
        "version": 1,
        "login": login,
        "repositories": {"own": own, "forks": forks},
        "languages": dict(sorted(languages.items())),
        "months": months,
    }
