"""Posta no Discord a edição do dia do Compilado do Código Fonte TV (principais notícias da semana)."""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from common import http_get, load_dotenv, load_state, save_state, send_webhook

HOME_URL = "https://compilado.codigofonte.com.br/"
YOUTUBE_URL = "https://www.youtube.com/@CompiladoPodcast"
SPOTIFY_URL = "https://open.spotify.com/show/7kLgm2CDG4aontuQOluFwb"
STATE_FILE = Path(__file__).with_name("posted_compilado.json")
BRT = timezone(timedelta(hours=-3))  # Brasília, sem horário de verão
EMBED_COLOR = 0xF26522


def fetch_editions():
    """Edições listadas na home, da mais antiga para a mais nova.

    O site (Pingback/Next.js) não tem RSS; a lista vem no JSON embutido em __NEXT_DATA__.
    O conteúdo das edições é só para inscritos, mas o título já traz as manchetes separadas por ';'.
    """
    page = http_get(HOME_URL).decode("utf-8")
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise RuntimeError("Não encontrei __NEXT_DATA__ na home do Compilado (o site mudou?)")
    articles = json.loads(m[1])["props"]["pageProps"]["channelProps"]["homeData"]["articles"]

    editions = []
    for a in articles:
        if not a.get("publishedDate"):
            continue
        name, _, rest = a["title"].partition(" - ")
        editions.append({
            "uid": a["uid"],
            "name": name.strip(),
            "headlines": [h.strip() for h in rest.split(";") if h.strip()],
            "title": a["title"],
            "link": HOME_URL + a["slug"],
            "image": a.get("bannerUrl"),
            "published": datetime.fromisoformat(a["publishedDate"].replace("Z", "+00:00")),
        })
    return sorted(editions, key=lambda e: e["published"])


def build_embed(ed):
    headlines = "\n".join(f"• {h}" for h in ed["headlines"]) or ed["title"]
    links = f"[Ler edição]({ed['link']}) · [YouTube]({YOUTUBE_URL}) · [Spotify]({SPOTIFY_URL})"
    embed = {
        "title": ed["name"][:256],
        "url": ed["link"],
        "description": f"{headlines}\n\n{links}"[:4096],
        "color": EMBED_COLOR,
        "timestamp": ed["published"].isoformat(),
        "footer": {"text": "Compilado do Código Fonte TV"},
    }
    if ed["image"]:
        embed["image"] = {"url": ed["image"]}
    return embed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que seria postado")
    parser.add_argument("--test", type=int, nargs="?", const=1, metavar="N",
                        help="posta as N edições mais recentes (padrão 1) ignorando o estado (e sem alterá-lo)")
    args = parser.parse_args()
    load_dotenv()

    editions = fetch_editions()
    today = datetime.now(BRT).date()
    posted = load_state(STATE_FILE)

    if args.test:
        new = editions[-args.test:]
    else:
        if posted is None:
            # Primeira execução: marca como enviadas as edições anteriores a hoje, pra só
            # postar a do dia (se houver) em vez de despejar o histórico no canal.
            posted = {e["uid"] for e in editions if e["published"].astimezone(BRT).date() < today}
        # Tudo que não foi enviado ainda. Normalmente é só a edição de hoje, mas assim também
        # pega uma edição publicada perto da meia-noite que só será vista na execução seguinte.
        new = [e for e in editions if e["uid"] not in posted]

    print(f"{len(editions)} edições na home, {len(new)} para postar (hoje: {today:%d/%m/%Y}).")

    if args.dry_run:
        for ed in new:
            print(f"\n{ed['name']} — publicada em {ed['published'].astimezone(BRT):%d/%m/%Y %H:%M}\n  {ed['link']}")
            for h in ed["headlines"]:
                print(f"  • {h}")
        return

    webhook_url = os.environ.get("DISCORD_WEBHOOK_COMPILADO_URL")
    if not webhook_url:
        sys.exit("Defina a variável de ambiente DISCORD_WEBHOOK_COMPILADO_URL.")

    try:
        for ed in new:
            send_webhook(webhook_url, {
                "username": "Compilado do Código Fonte TV",
                "embeds": [build_embed(ed)],
                "allowed_mentions": {"parse": []},
            })
            if posted is not None:
                posted.add(ed["uid"])
            print(f"Postado: {ed['name']}")
            time.sleep(1)
    finally:
        if not args.test:
            save_state(STATE_FILE, posted)


if __name__ == "__main__":
    main()
