"""Refresh live public data or reproduce the profile from the checked-in snapshot."""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import ParseError

from .calendar import daily_activity, fetch_calendar
from .data import collect
from .github import GitHub, GitHubError
from .model import read_json, validate_config
from .render import build, publish

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--refresh", action="store_true", help="consultar a API REST pública")
    mode.add_argument("--check", action="store_true", help="comparar os arquivos com a geração offline")
    parser.add_argument("--output", type=Path, default=ROOT, help="diretório dos arquivos gerados")
    parser.add_argument("--static", action="store_true", help="gerar SVGs sem animação para uma prévia")
    args = parser.parse_args()
    if args.static and args.output.resolve() == ROOT:
        parser.error("--static requer um --output diferente da raiz do repositório.")

    try:
        config = read_json(ROOT / "config/profile.json")
        themes = read_json(ROOT / "config/theme.json")
        template = (ROOT / "profile_readme/readme.md.in").read_text(encoding="utf-8")
        validate_config(config, themes)
        if args.refresh:
            print("Consultando repositórios, commits e calendário público no GitHub.", flush=True)
            api = GitHub(os.getenv("GITHUB_TOKEN"))
            today = datetime.now(timezone.utc).date()
            snapshot = collect(api, config["login"], today)
            calendar = fetch_calendar(config["login"])
            end = max(day for day, _, _ in daily_activity(calendar))
            if abs((today - end).days) > 1:
                raise GitHubError("O calendário público retornado está desatualizado.")
        else:
            snapshot = read_json(ROOT / "data/public.json")
            calendar = read_json(ROOT / "data/calendar.json")
        files = build(config, themes, template, snapshot, calendar, static=args.static)
        changed = publish(args.output, files, check=args.check)
    except GitHubError as error:
        print(f"Atualização interrompida. {error}", file=sys.stderr)
        return 1
    except (KeyError, OSError, TypeError, ValueError, ParseError) as error:
        print(f"Falha ao processar configuração, dados ou arquivos ({type(error).__name__}).", file=sys.stderr)
        return 1

    if args.check and changed:
        print("Arquivos fora de sincronia: " + ", ".join(changed), file=sys.stderr)
        return 1
    print(f"{len(files)} arquivos verificados. {len(changed)} atualizados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
