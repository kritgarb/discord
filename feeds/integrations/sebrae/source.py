"""Fontes das missões do Sebrae/SE (Agência de Notícias e Portal Sebrae) e leitura dos editais."""

from __future__ import annotations

import html
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from pypdf import PdfReader

from feeds.core.http import HttpClient
from feeds.integrations.sebrae import parsing
from feeds.integrations.sebrae.models import PORTAL, Mission

NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


class SebraeFeed:
    """Feed RSS principal do site.

    Não usamos a busca (?s=): o índice dela está desatualizado e perde posts.
    """

    URL = "https://se.agenciasebrae.com.br/feed/"

    def __init__(self, http: HttpClient):
        self.http = http

    def page(self, number: int) -> list[Mission]:
        try:
            root = ET.fromstring(self.http.get(self.URL, {"paged": number}))
        except urllib.error.HTTPError as e:
            if e.code == 404:  # além da última página
                return []
            raise
        return [self._parse_item(item) for item in root.iter("item")]

    @staticmethod
    def _parse_item(item: ET.Element) -> Mission:
        media = item.find("media:content", NS)
        return Mission(
            guid=(item.findtext("guid") or item.findtext("link")).strip(),
            title=parsing.clean_text(item.findtext("title")),
            link=item.findtext("link").strip(),
            description=parsing.clean_text(item.findtext("description")),
            content_html=item.findtext("content:encoded", namespaces=NS) or "",
            published=parsedate_to_datetime(item.findtext("pubDate")),
            image=media.get("url") if media is not None else None,
        )


def parse_portal_model(data: dict, url: str, base_url: str = "https://sebrae.com.br") -> Mission:
    """Monta a Mission a partir do .model.json de uma página do Portal Sebrae (Adobe AEM).

    O conteúdo fica na árvore ':items' do 'responsivegrid': componentes de texto (HTML) e
    botões/ações com links (edital em PDF, formulário). Os links viram <a> no content_html
    para o MissionExtractor tratar igual a uma notícia da Agência.
    """
    grid = data.get(":items", {}).get("root", {}).get(":items", {}).get("responsivegrid", {})
    texts: list[str] = []
    links: list[tuple[str, str]] = []

    def absolute(href: str) -> str:
        return urllib.parse.urljoin(base_url, urllib.parse.quote(href, safe="/%:?=&#"))

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("link"), str):                    # botão
                links.append((absolute(node["link"]), node.get("text") or ""))
            elif isinstance(node.get("url"), str) and "title" in node:  # ação de teaser
                links.append((absolute(node["url"]), node.get("title") or ""))
            elif isinstance(node.get("text"), str) and "<" in node["text"]:  # componente de texto (HTML)
                texts.append(node["text"])
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(grid)
    content_html = "".join(texts) + "".join(
        f'<p><a href="{html.escape(href)}">{html.escape(label)}</a></p>' for href, label in links
    )
    modified = data.get("lastModifiedDate")
    published = (datetime.fromtimestamp(modified / 1000, tz=timezone.utc) if modified
                 else datetime.now(timezone.utc))
    return Mission(
        guid=url,
        title=parsing.clean_text(data.get("title")),
        link=url,
        description=parsing.clean_text(data.get("description")),
        content_html=content_html,
        published=published,
        source=PORTAL,
    )


class SebraePortal:
    """Portal Sebrae (sebrae.com.br), onde o Sebrae/SE também publica missões.

    Não tem RSS: as páginas de missão vêm do sitemap e o conteúdo, do .model.json de cada uma.
    """

    BASE_URL = "https://sebrae.com.br"
    SITEMAP_URL = BASE_URL + "/sitemap.xml"
    MISSION_URL_RE = re.compile(r"^https://sebrae\.com\.br/se/subsites/.*miss", re.IGNORECASE)

    def __init__(self, http: HttpClient):
        self.http = http

    def mission_urls(self) -> list[str]:
        sitemap = self.http.get_text(self.SITEMAP_URL)
        return [u for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap) if self.MISSION_URL_RE.match(u)]

    def mission(self, url: str) -> Mission:
        return parse_portal_model(json.loads(self.http.get(url + ".model.json")), url, self.BASE_URL)


class MissionExtractor:
    """Preenche os detalhes de uma missão a partir da página da notícia e do edital em PDF."""

    def __init__(self, http: HttpClient):
        self.http = http

    def article_html(self, url: str) -> str | None:
        """Corpo da notícia direto da página (o content:encoded do RSS às vezes vem desatualizado)."""
        try:
            page = self.http.get_text(url)
        except Exception:
            return None
        m = re.search(r'<div class="text-content">(.*?)</div>', page, re.S)
        return m[1] if m else None

    def pdf_text(self, url: str) -> str:
        reader = PdfReader(io.BytesIO(self.http.get(url)))
        return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in reader.pages))

    def extract(self, mission: Mission) -> Mission:
        content_html = mission.content_html
        if mission.source != PORTAL:  # o portal já vem completo do .model.json
            content_html = self.article_html(mission.link) or content_html
        body = parsing.clean_text(content_html)
        intro = parsing.first_paragraph(content_html)

        mission.event = parsing.extract_event(intro)
        mission.location = parsing.extract_location(intro)
        mission.dates = parsing.extract_event_dates(intro)
        mission.edital_url = parsing.find_edital_url(content_html)
        mission.signup_url = parsing.find_signup_url(content_html)

        deadlines = parsing.deadline_candidates(body + " " + mission.description)
        if mission.edital_url:
            try:
                edital = self.pdf_text(mission.edital_url)
            except Exception as e:  # PDF fora do ar ou ilegível não deve travar o post
                print(f"  aviso: não consegui ler o edital ({e})", file=sys.stderr)
            else:
                mission.price = parsing.extract_price(edital)
                mission.location = mission.location or parsing.extract_location(edital)
                mission.dates = mission.dates or parsing.extract_event_dates(edital)
                deadlines += parsing.deadline_candidates(edital)
        # o prazo vigente é o mais recente entre notícia, prorrogações e erratas
        mission.deadline = max(deadlines) if deadlines else None
        return mission
