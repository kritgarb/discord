from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


AGENCIA = "agencia"  # Agência Sebrae de Notícias (feed RSS)
PORTAL = "portal"    # Portal Sebrae (sebrae.com.br/se/subsites/...)


@dataclass
class Mission:
    """Missão empresarial encontrada numa das fontes; os detalhes são preenchidos pelo MissionExtractor."""

    guid: str
    title: str
    link: str
    description: str
    content_html: str
    published: datetime
    image: str | None = None
    source: str = AGENCIA

    # detalhes extraídos da notícia e do edital
    event: str | None = None
    location: str | None = None
    dates: str | None = None
    price: str | None = None
    deadline: date | None = None
    edital_url: str | None = None
    signup_url: str | None = None
