from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from feeds.core.http import HttpClient
from feeds.core.integration import Integration
from feeds.core.state import SeenStore
from feeds.integrations.compilado.models import Edition
from feeds.integrations.compilado.source import CompiladoSite

BRT = timezone(timedelta(hours=-3))  # Brasília, sem horário de verão


class Compilado(Integration[Edition]):
    """Edição do dia do Compilado do Código Fonte TV (principais notícias da semana)."""

    slug = "compilado"
    title = "Compilado do Código Fonte TV"
    username = "Compilado do Código Fonte TV"
    webhook_env = "DISCORD_WEBHOOK_COMPILADO_URL"

    YOUTUBE_URL = "https://www.youtube.com/@CompiladoPodcast"
    SPOTIFY_URL = "https://open.spotify.com/show/7kLgm2CDG4aontuQOluFwb"
    EMBED_COLOR = 0xF26522

    def __init__(self, http: HttpClient, state: SeenStore, **kwargs):
        super().__init__(http, state, **kwargs)
        self.site = CompiladoSite(http)

    @staticmethod
    def today() -> date:
        return datetime.now(BRT).date()

    def fetch(self, *, full, limit):
        return self.site.editions()  # a home já lista as últimas 12; não há paginação

    def keys(self, item):
        return {item.uid}

    def label(self, item):
        return item.name

    def bootstrap(self, items):
        # Primeira execução: as edições anteriores a hoje contam como enviadas,
        # pra só postar a do dia (se houver) em vez de despejar o histórico.
        today = self.today()
        return [e for e in items if e.published.astimezone(BRT).date() < today]

    def to_embed(self, item):
        headlines = "\n".join(f"• {h}" for h in item.headlines) or item.title
        links = f"[Ler edição]({item.link}) · [YouTube]({self.YOUTUBE_URL}) · [Spotify]({self.SPOTIFY_URL})"
        embed = {
            "title": item.name[:256],
            "url": item.link,
            "description": f"{headlines}\n\n{links}"[:4096],
            "color": self.EMBED_COLOR,
            "timestamp": item.published.isoformat(),
            "footer": {"text": "Compilado do Código Fonte TV"},
        }
        if item.image:
            embed["image"] = {"url": item.image}
        return embed

    def summary(self, item):
        published = item.published.astimezone(BRT).strftime("%d/%m/%Y %H:%M")
        return [f"{item.name} — publicada em {published}", f"  {item.link}"] + [f"  • {h}" for h in item.headlines]
