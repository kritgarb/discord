from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Edition:
    """Edição do Compilado do Código Fonte TV."""

    uid: str
    name: str                 # "COMPILADO #263"
    title: str                # título completo, com as manchetes
    link: str
    published: datetime       # UTC
    image: str | None = None
    headlines: list[str] = field(default_factory=list)
