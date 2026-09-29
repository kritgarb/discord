from __future__ import annotations

import re

from feeds.core import clock
from feeds.core.http import HttpClient
from feeds.core.integration import Integration
from feeds.core.state import SeenStore
from feeds.integrations.sebrae import parsing
from feeds.integrations.sebrae.models import PORTAL, Mission
from feeds.integrations.sebrae.source import MissionExtractor, SebraeFeed, SebraePortal


class SebraeMissoes(Integration[Mission]):
    """Missões empresariais do Sebrae/SE, publicadas na Agência Sebrae de Notícias e/ou no Portal Sebrae."""

    slug = "missoes"
    title = "Missões Sebrae/SE"
    username = "Missões Sebrae/SE"
    webhook_env = "DISCORD_WEBHOOK_URL"

    MISSION_RE = re.compile(r"\bmiss(ão|ões|ao|oes)\b", re.IGNORECASE)
    PAGES_PER_RUN = 3        # ≈ 30 posts, suficiente para rodar de hora em hora
    MAX_PAGES_FULL = 30      # primeira execução / --test
    EMBED_COLOR = 0x005EB8
    FOOTERS = {
        PORTAL: "Portal Sebrae · Sergipe",
    }
    DEFAULT_FOOTER = "Agência Sebrae de Notícias · Sergipe"

    def __init__(self, http: HttpClient, state: SeenStore, **kwargs):
        super().__init__(http, state, **kwargs)
        self.feed = SebraeFeed(http)
        self.portal = SebraePortal(http)
        self.extractor = MissionExtractor(http)

    # ----- busca -----

    def fetch(self, *, full, limit):
        # A mesma missão pode sair nas duas fontes: agrupa pelo título normalizado.
        found: dict[str, Mission] = {}
        for mission in [*self._from_agencia(full, limit), *self._from_portal(full)]:
            found.setdefault(parsing.title_key(mission.title), mission)
        return sorted(found.values(), key=lambda m: m.published)

    def _from_agencia(self, full: bool, limit: int | None) -> list[Mission]:
        found: list[Mission] = []
        for number in range(1, (self.MAX_PAGES_FULL if full else self.PAGES_PER_RUN) + 1):
            posts = self.feed.page(number)
            if not posts:
                break
            found += [p for p in posts if self.MISSION_RE.search(p.title)]
            if limit and len(found) >= limit:
                break
        return found

    def _from_portal(self, full: bool) -> list[Mission]:
        found = []
        for url in self.portal.mission_urls():
            if not full and self.state.contains_any({url}):
                continue  # já visto: não precisa baixar a página de novo
            try:
                mission = self.portal.mission(url)
            except Exception as e:  # uma página com problema não derruba as outras
                self.log(f"[{self.title}] aviso: não consegui ler {url} ({e})")
                continue
            if self.MISSION_RE.search(mission.title):
                found.append(mission)
        return found

    # ----- regras -----

    def keys(self, item):
        # guid, link e título normalizado: qualquer um já identifica a missão como enviada,
        # inclusive quando ela aparece na outra fonte
        return {item.guid, item.link, parsing.title_key(item.title)}

    def label(self, item):
        return item.title

    def enrich(self, item):
        return self.extractor.extract(item)

    def skip_reason(self, item):
        if item.deadline and item.deadline < clock.today():
            return f"inscrições encerradas em {item.deadline:%d/%m/%Y}"
        return None

    # ----- apresentação -----

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
        links = [f"[{'Página' if item.source == PORTAL else 'Notícia'}]({item.link})"]
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
            "footer": {"text": self.FOOTERS.get(item.source, self.DEFAULT_FOOTER)},
        }
        if len(fields) < 2:  # página fora do modelo padrão: mostra o resumo
            embed["description"] = item.description[:4096]
        if item.image:
            embed["thumbnail"] = {"url": item.image}
        return embed

    def summary(self, item):
        return [item.title, f"  {item.link}"] + [f"  {n}: {v}" for n, v in self.fields(item)]
