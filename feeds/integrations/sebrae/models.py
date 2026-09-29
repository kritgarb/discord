from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Mission:
    """Post de missão empresarial do feed; os detalhes são preenchidos pelo MissionExtractor."""

    guid: str
    title: str
    link: str
    description: str
    content_html: str
    published: datetime
    image: str | None = None

    # detalhes extraídos da notícia e do edital
    event: str | None = None
    location: str | None = None
    dates: str | None = None
    price: str | None = None
    deadline: date | None = None
    edital_url: str | None = None
    signup_url: str | None = None
