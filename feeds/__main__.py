"""CLI: python -m feeds {missoes,compilado,all} [--dry-run] [--test [N]]"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from feeds.core import ConfigError, HttpClient, SeenStore, load_dotenv
from feeds.integrations import INTEGRATIONS

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m feeds", description="Publica feeds no Discord.")
    parser.add_argument("integration", choices=[*INTEGRATIONS, "all"],
                        help="integração a executar ('all' roda todas)")
    parser.add_argument("--dry-run", action="store_true",
                        help="só mostra o que seria postado, sem enviar nem salvar estado")
    parser.add_argument("--test", type=int, nargs="?", const=1, metavar="N",
                        help="envia os N itens mais recentes (padrão 1) mesmo que já enviados, sem alterar o estado")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(ROOT / ".env")

    http = HttpClient()
    slugs = list(INTEGRATIONS) if args.integration == "all" else [args.integration]
    failed = []
    for slug in slugs:
        integration = INTEGRATIONS[slug](http, SeenStore(STATE_DIR / f"{slug}.json"))
        try:
            integration.run(dry_run=args.dry_run, test=args.test)
        except ConfigError as e:
            print(f"[{integration.title}] {e}", file=sys.stderr)
            failed.append(slug)
        except Exception:  # uma integração com problema não impede as outras
            print(f"[{integration.title}] falhou:", file=sys.stderr)
            traceback.print_exc()
            failed.append(slug)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
