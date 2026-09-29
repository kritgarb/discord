"""Leitura das edições do Compilado a partir da home do site."""

from __future__ import annotations

import json
import re
from datetime import datetime

from feeds.core.http import HttpClient
from feeds.integrations.compilado.models import Edition


def split_title(title: str) -> tuple[str, list[str]]:
    """'COMPILADO #263 - A; B; C' → ('COMPILADO #263', ['A', 'B', 'C'])."""
    name, _, rest = title.partition(" - ")
    return name.strip(), [h.strip() for h in rest.split(";") if h.strip()]


def parse_home(page_html: str, base_url: str) -> list[Edition]:
    """Edições publicadas listadas no JSON __NEXT_DATA__ da home, da mais antiga para a mais nova."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page_html, re.S)
    if not m:
        raise RuntimeError("Não encontrei __NEXT_DATA__ na home do Compilado (o site mudou?)")
    articles = json.loads(m[1])["props"]["pageProps"]["channelProps"]["homeData"]["articles"]

    editions = []
    for a in articles:
        if not a.get("publishedDate"):
            continue
        name, headlines = split_title(a["title"])
        editions.append(Edition(
            uid=a["uid"],
            name=name,
            title=a["title"],
            link=base_url + a["slug"],
            published=datetime.fromisoformat(a["publishedDate"].replace("Z", "+00:00")),
            image=a.get("bannerUrl"),
            headlines=headlines,
        ))
    return sorted(editions, key=lambda e: e.published)


class CompiladoSite:
    """O site (plataforma Pingback/Next.js) não tem RSS; a lista vem embutida na home.

    O texto das edições é só para inscritos, mas o título já traz as manchetes separadas por ';'.
    """

    URL = "https://compilado.codigofonte.com.br/"

    def __init__(self, http: HttpClient):
        self.http = http

    def editions(self) -> list[Edition]:
        return parse_home(self.http.get_text(self.URL), self.URL)
