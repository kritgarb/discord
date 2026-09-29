"""Busca missões empresariais no feed RSS da Agência Sebrae (SE) e publica no Discord via webhook."""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

BASE_URL = "https://se.agenciasebrae.com.br/"
SEARCH_TERMS = ["missão", "missões"]
MISSION_RE = re.compile(r"\bmiss(ão|ões|ao|oes)\b", re.IGNORECASE)
STATE_FILE = Path(__file__).with_name("posted.json")
USER_AGENT = "Mozilla/5.0 (compatible; sebrae-missoes-discord/1.0)"
NS = {"media": "http://search.yahoo.com/mrss/"}
EMBED_COLOR = 0x005EB8
PAGES_PER_RUN = 3
MAX_PAGES_FIRST_RUN = 30


def load_dotenv(path=Path(__file__).with_name(".env")):
    """Carrega KEY=valor do .env sem sobrescrever variáveis já definidas (ex.: secrets do Actions)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def clean_text(raw):
    text = html.unescape(re.sub(r"<[^>]+>", "", raw or ""))
    text = text.replace("[…]", "…").replace("[...]", "…")
    return re.sub(r"\s+", " ", text).strip()


def fetch_page(term, page):
    params = {"s": term, "feed": "rss2", "paged": page}
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    try:
        root = ET.fromstring(http_get(url))
    except urllib.error.HTTPError as e:
        if e.code == 404:  # página além do fim da busca
            return []
        raise

    items = []
    for item in root.iter("item"):
        media = item.find("media:content", NS)
        items.append({
            "guid": (item.findtext("guid") or item.findtext("link")).strip(),
            "title": clean_text(item.findtext("title")),
            "link": item.findtext("link").strip(),
            "description": clean_text(item.findtext("description")),
            "pub_date": parsedate_to_datetime(item.findtext("pubDate")),
            "image": media.get("url") if media is not None else None,
        })
    return items


def fetch_missions(max_pages):
    found = {}
    for term in SEARCH_TERMS:
        for page in range(1, max_pages + 1):
            items = fetch_page(term, page)
            if not items:
                break
            for it in items:
                if MISSION_RE.search(it["title"]):
                    found[it["guid"]] = it
    return sorted(found.values(), key=lambda it: it["pub_date"])


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(posted):
    STATE_FILE.write_text(json.dumps(sorted(posted), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_embed(it):
    embed = {
        "title": it["title"][:256],
        "url": it["link"],
        "description": it["description"][:4096],
        "color": EMBED_COLOR,
        "timestamp": it["pub_date"].isoformat(),
        "footer": {"text": "Agência Sebrae de Notícias · Sergipe"},
    }
    if it["image"]:
        embed["image"] = {"url": it["image"]}
    return embed


def post_to_discord(webhook_url, it):
    payload = json.dumps({
        "username": "Missões Sebrae/SE",
        "embeds": [build_embed(it)],
        "allowed_mentions": {"parse": []},
    }).encode("utf-8")
    for _ in range(5):
        req = urllib.request.Request(
            webhook_url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            urllib.request.urlopen(req, timeout=30).close()
            return
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            retry_after = json.loads(e.read() or b"{}").get("retry_after", 2)
            time.sleep(float(retry_after) + 0.5)
    raise RuntimeError(f"Rate limit persistente ao postar: {it['title']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="só lista o que seria postado")
    args = parser.parse_args()
    load_dotenv()

    state = load_state()
    first_run = state is None
    posted = set(state or [])

    missions = fetch_missions(MAX_PAGES_FIRST_RUN if first_run else PAGES_PER_RUN)
    new = [it for it in missions if it["guid"] not in posted]
    print(f"{len(missions)} missões encontradas, {len(new)} novas.")

    if args.dry_run:
        for it in new:
            print(f"- {it['pub_date']:%Y-%m-%d} {it['title']}\n  {it['link']}")
        return

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        sys.exit("Defina a variável de ambiente DISCORD_WEBHOOK_URL.")

    try:
        for it in new:
            post_to_discord(webhook_url, it)
            posted.add(it["guid"])
            print(f"Postado: {it['title']}")
            time.sleep(1)
    finally:
        # salva mesmo se falhar no meio, pra não repetir o que já foi
        save_state(posted)


if __name__ == "__main__":
    main()
