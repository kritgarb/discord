"""Acesso ao site da Agência Sebrae de Notícias (SE): feed RSS, páginas e editais."""

from __future__ import annotations

import io
import re
import sys
import urllib.error
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from pypdf import PdfReader

from feeds.core.http import HttpClient
from feeds.integrations.sebrae import parsing
from feeds.integrations.sebrae.models import Mission

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
        content_html = self.article_html(mission.link) or mission.content_html
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
