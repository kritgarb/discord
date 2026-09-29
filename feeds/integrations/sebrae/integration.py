from __future__ import annotations

import re

from feeds.core.http import HttpClient
from feeds.core.integration import Integration
from feeds.core.state import SeenStore
from feeds.integrations.sebrae.models import Mission
from feeds.integrations.sebrae.source import MissionExtractor, SebraeFeed


class SebraeMissoes(Integration[Mission]):
    """Missões empresariais publicadas na Agência Sebrae de Notícias (SE)."""

    slug = "missoes"
    title = "Missões Sebrae/SE"
    username = "Missões Sebrae/SE"
    webhook_env = "DISCORD_WEBHOOK_URL"

    MISSION_RE = re.compile(r"\bmiss(ão|ões|ao|oes)\b", re.IGNORECASE)
    PAGES_PER_RUN = 3        # ≈ 30 posts, suficiente para rodar de hora em hora
    MAX_PAGES_FULL = 30      # primeira execução / --test
    EMBED_COLOR = 0x005EB8

    def __init__(self, http: HttpClient, state: SeenStore, **kwargs):
        super().__init__(http, state, **kwargs)
        self.feed = SebraeFeed(http)
        self.extractor = MissionExtractor(http)

    def fetch(self, *, full, limit):
        found: dict[str, Mission] = {}
        for number in range(1, (self.MAX_PAGES_FULL if full else self.PAGES_PER_RUN) + 1):
            posts = self.feed.page(number)
            if not posts:
                break
            for post in posts:
                if self.MISSION_RE.search(post.title):
                    found[post.guid] = post
            if limit and len(found) >= limit:
                break
        return sorted(found.values(), key=lambda m: m.published)

    def keys(self, item):
        # guid (?p=ID) e link: qualquer um dos dois já identifica a missão como enviada
        return {item.guid, item.link}

    def label(self, item):
        return item.title

    def enrich(self, item):
        return self.extractor.extract(item)

    def fields(self, item: Mission) -> list[tuple[str, str]]:
        fields = [
            ("🎯 Evento", item.event),
            ("📍 Local", item.location),
            ("📅 Data", item.dates),
            ("💰 Valor (participante)", item.price and f"≈ {item.price}"),
            ("⏰ Inscrições até", item.deadline and item.deadline.strftime("%d/%m/%Y")),
        ]
        return [(name, value) for name, value in fields if value]

    def to_embed(self, item):
        fields = self.fields(item)
        links = [f"[Notícia]({item.link})"]
        if item.edital_url:
            links.append(f"[Edital]({item.edital_url})")
        if item.signup_url:
            links.append(f"[Inscrição]({item.signup_url})")

        embed = {
            "title": item.title[:256],
            "url": item.link,
            "color": self.EMBED_COLOR,
            "fields": [{"name": n, "value": v[:1024], "inline": True} for n, v in fields]
                      + [{"name": "🔗 Links", "value": " · ".join(links), "inline": False}],
            "timestamp": item.published.isoformat(),
            "footer": {"text": "Agência Sebrae de Notícias · Sergipe"},
        }
        if len(fields) < 2:  # post fora do modelo padrão: mostra o resumo
            embed["description"] = item.description[:4096]
        if item.image:
            embed["thumbnail"] = {"url": item.image}
        return embed

    def summary(self, item):
        return [item.title, f"  {item.link}"] + [f"  {n}: {v}" for n, v in self.fields(item)]
