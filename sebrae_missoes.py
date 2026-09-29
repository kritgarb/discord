"""Busca missões empresariais no feed RSS da Agência Sebrae (SE) e publica no Discord via webhook."""

import argparse
import html
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

from pypdf import PdfReader

FEED_URL = "https://se.agenciasebrae.com.br/feed/"
MISSION_RE = re.compile(r"\bmiss(ão|ões|ao|oes)\b", re.IGNORECASE)
STATE_FILE = Path(__file__).with_name("posted.json")
USER_AGENT = "Mozilla/5.0 (compatible; sebrae-missoes-discord/1.0)"
NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}
EMBED_COLOR = 0x005EB8
PAGES_PER_RUN = 3
MAX_PAGES_FIRST_RUN = 30

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
DATE_NUM_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4}|\d{2})\b")
DATE_EXT_RE = re.compile(r"(\d{1,2})º?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", re.IGNORECASE)


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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def clean_text(raw):
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = text.replace("[…]", "…").replace("[...]", "…")
    return re.sub(r"\s+", " ", text).strip()


# ---------- Extração dos detalhes ----------

def parse_dates(text):
    """Retorna todas as datas (numéricas ou por extenso) encontradas no texto, na ordem."""
    found = []
    for m in DATE_NUM_RE.finditer(text):
        d, mth, y = int(m[1]), int(m[2]), int(m[3])
        found.append((m.start(), y + 2000 if y < 100 else y, mth, d))
    for m in DATE_EXT_RE.finditer(text):
        mth = MESES.get(m[2].lower())
        if mth:
            found.append((m.start(), int(m[3]), mth, int(m[1])))
    dates = []
    for _, y, mth, d in sorted(found):
        try:
            dates.append(date(y, mth, d))
        except ValueError:
            pass
    return dates


def deadline_candidates(text):
    """Datas-limite de inscrição mencionadas no texto (fim de cada período/prorrogação)."""
    patterns = [
        r"prorrogad[oa] até ([^.;]+)",
        r"inscri\w+ será de ([^,;]+)",
        r"disponível de ([^,;]+)",
        r"inscrev\w+(?:-se)? até ([^.;]+)",
    ]
    out = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            dates = parse_dates(m[1])
            if dates:
                out.append(dates[-1])
    return out


def pdf_text(url):
    reader = PdfReader(io.BytesIO(http_get(url)))
    return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in reader.pages))


def find_edital_url(content_html):
    """Último link de edital no post (erratas/versões alteradas vêm depois do original)."""
    edital = None
    for href, label in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', content_html, re.S):
        label = clean_text(label).lower()
        if href.lower().endswith(".pdf") and "edital" in (label + href.lower()) and "resultado" not in label:
            edital = href.replace("http://", "https://", 1)
    return edital


def find_signup_url(content_html):
    m = re.search(r'href="(https://forms\.[^"]+)"', content_html)
    return m[1] if m else None


def extract_event(intro):
    """Nome do evento a partir do 1º parágrafo ('levará empreendedores ao X, <descrição>, que acontecerá...')."""
    m = re.search(
        r"levará empreendedores (?:\w+ )?(?:para o|para a|ao|à|no|na|a)\s+(.+?)\s*,\s+.+?,?\s+que acontecer",
        intro, re.IGNORECASE,
    )
    return m[1].strip() if m else None


def extract_location(text):
    m = re.search(r"na cidade d[eoa]s?\s+([A-ZÀ-Ý][^,.;]+?)(?:\s*[,.;]|\s+no período)", text, re.IGNORECASE)
    if not m:
        return None
    return re.sub(r"\s*\((\w{2})\)", r"/\1", m[1].strip())


def extract_event_dates(text):
    m = re.search(
        r"\d{1,2}(?:º)?(?:\s+de\s+[a-zç]+)?\s+(?:a|e)\s+\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}"
        r"|\d{1,2}(?:º)?\s+de\s+[a-zç]+\s+de\s+\d{4}",
        text, re.IGNORECASE,
    )
    return m[0] if m else None


def extract_price(edital_text):
    m = re.search(
        r"valor a ser pago pelo participante.{0,60}?R\s*\$\s*([\d.]+,\d{2})",
        edital_text, re.IGNORECASE,
    )
    return f"R$ {m[1]}" if m else None


def fetch_article_html(url):
    """Corpo da notícia direto da página (o content:encoded do RSS às vezes vem desatualizado)."""
    try:
        page = http_get(url).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r'<div class="text-content">(.*?)</div>', page, re.S)
    return m[1] if m else None


def enrich(it):
    """Preenche evento, tipo, local, data, valor, prazo e links a partir do post e do edital."""
    content_html = fetch_article_html(it["link"]) or it["content"]
    body = clean_text(content_html)
    intro = clean_text(content_html.split("</p>", 1)[0])

    it["event"] = extract_event(intro)
    it["location"] = extract_location(intro)
    it["dates"] = extract_event_dates(intro)
    it["edital"] = find_edital_url(content_html)
    it["signup"] = find_signup_url(content_html)
    it["price"] = None

    deadlines = deadline_candidates(body + " " + it["description"])
    if it["edital"]:
        try:
            edital = pdf_text(it["edital"])
        except Exception as e:  # PDF fora do ar ou ilegível não deve travar o post
            print(f"  aviso: não consegui ler o edital ({e})", file=sys.stderr)
        else:
            it["price"] = extract_price(edital)
            it["location"] = it["location"] or extract_location(edital)
            it["dates"] = it["dates"] or extract_event_dates(edital)
            deadlines += deadline_candidates(edital)
    it["deadline"] = max(deadlines) if deadlines else None
    return it


# ---------- Feed ----------

def fetch_page(page):
    # A busca do site (?s=) tem índice desatualizado e perde posts; o feed principal paginado é completo.
    url = FEED_URL + "?" + urllib.parse.urlencode({"paged": page})
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
            "content": item.findtext("content:encoded", namespaces=NS) or "",
            "pub_date": parsedate_to_datetime(item.findtext("pubDate")),
            "image": media.get("url") if media is not None else None,
        })
    return items


def fetch_missions(max_pages, stop_after=None):
    found = {}
    for page in range(1, max_pages + 1):
        items = fetch_page(page)
        if not items:
            break
        for it in items:
            if MISSION_RE.search(it["title"]):
                found[it["guid"]] = it
        if stop_after and len(found) >= stop_after:
            break
    return sorted(found.values(), key=lambda it: it["pub_date"])


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_state(posted):
    STATE_FILE.write_text(json.dumps(sorted(posted), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------- Discord ----------

def summary_fields(it):
    fields = [
        ("🎯 Evento", it["event"]),
        ("📍 Local", it["location"]),
        ("📅 Data", it["dates"]),
        ("💰 Valor (participante)", it["price"] and f"≈ {it['price']}"),
        ("⏰ Inscrições até", it["deadline"] and it["deadline"].strftime("%d/%m/%Y")),
    ]
    return [(name, value) for name, value in fields if value]


def build_embed(it):
    fields = summary_fields(it)
    links = [f"[Notícia]({it['link']})"]
    if it["edital"]:
        links.append(f"[Edital]({it['edital']})")
    if it["signup"]:
        links.append(f"[Inscrição]({it['signup']})")

    embed = {
        "title": it["title"][:256],
        "url": it["link"],
        "color": EMBED_COLOR,
        "fields": [{"name": n, "value": v[:1024], "inline": True} for n, v in fields]
                  + [{"name": "🔗 Links", "value": " · ".join(links), "inline": False}],
        "timestamp": it["pub_date"].isoformat(),
        "footer": {"text": "Agência Sebrae de Notícias · Sergipe"},
    }
    if len(fields) < 2:  # post sem edital/estrutura padrão: mostra o resumo
        embed["description"] = it["description"][:4096]
    if it["image"]:
        embed["thumbnail"] = {"url": it["image"]}
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
    parser.add_argument("--dry-run", action="store_true", help="só mostra o que seria postado")
    parser.add_argument("--test", type=int, metavar="N",
                        help="pega as N missões mais recentes ignorando o posted.json (e sem alterá-lo)")
    args = parser.parse_args()
    load_dotenv()

    state = load_state()
    posted = set(state or [])
    deep_scan = state is None or args.test

    missions = fetch_missions(MAX_PAGES_FIRST_RUN if deep_scan else PAGES_PER_RUN, stop_after=args.test)
    if args.test:
        new = missions[-args.test:]
    else:
        # guid (?p=ID) e link são guardados: qualquer um dos dois já identifica como enviado
        new = [it for it in missions if not {it["guid"], it["link"]} & posted]
    print(f"{len(missions)} missões encontradas, {len(new)} para postar.")

    for it in new:
        enrich(it)

    if args.dry_run:
        for it in new:
            print(f"\n{it['title']}\n  {it['link']}")
            for name, value in summary_fields(it):
                print(f"  {name}: {value.replace(chr(10), ' — ')}")
        return

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        sys.exit("Defina a variável de ambiente DISCORD_WEBHOOK_URL.")

    try:
        for it in new:
            post_to_discord(webhook_url, it)
            posted.update({it["guid"], it["link"]})
            print(f"Postado: {it['title']}")
            time.sleep(1)
    finally:
        # salva mesmo se falhar no meio, pra não repetir o que já foi (exceto em modo teste)
        if not args.test:
            save_state(posted)


if __name__ == "__main__":
    main()
