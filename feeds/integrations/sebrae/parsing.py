"""Funções puras de extração de texto das notícias e editais do Sebrae/SE."""

from __future__ import annotations

import html
import re
from datetime import date

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
DATE_NUM_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4}|\d{2})\b")
DATE_EXT_RE = re.compile(r"(\d{1,2})º?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", re.IGNORECASE)
DEADLINE_PATTERNS = [
    r"prorrogad[oa] até ([^.;]+)",
    r"inscri\w+ será de ([^,;]+)",
    r"disponível de ([^,;]+)",
    r"inscrev\w+(?:-se)? até ([^.;]+)",
]


def clean_text(raw: str | None) -> str:
    """Remove tags HTML, decodifica entidades e normaliza espaços."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    text = text.replace("[…]", "…").replace("[...]", "…")
    return re.sub(r"\s+", " ", text).strip()


def first_paragraph(content_html: str) -> str:
    return clean_text(content_html.split("</p>", 1)[0])


def parse_dates(text: str) -> list[date]:
    """Todas as datas (dd/mm/aaaa ou 'dd de mês de aaaa') do texto, na ordem em que aparecem."""
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


def deadline_candidates(text: str) -> list[date]:
    """Fim de cada período de inscrição/prorrogação mencionado no texto."""
    out = []
    for pat in DEADLINE_PATTERNS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            dates = parse_dates(m[1])
            if dates:
                out.append(dates[-1])
    return out


def find_edital_url(content_html: str) -> str | None:
    """Último link de edital no post (erratas/versões alteradas vêm depois do original)."""
    edital = None
    for href, label in re.findall(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', content_html, re.S):
        label = clean_text(label).lower()
        if href.lower().endswith(".pdf") and "edital" in (label + href.lower()) and "resultado" not in label:
            edital = href.replace("http://", "https://", 1)
    return edital


def find_signup_url(content_html: str) -> str | None:
    m = re.search(r'href="(https://forms\.[^"]+)"', content_html)
    return m[1] if m else None


def extract_event(intro: str) -> str | None:
    """Nome do evento: 'levará empreendedores ao X, <descrição>, que acontecerá...'."""
    m = re.search(
        r"levará empreendedores (?:\w+ )?(?:para o|para a|ao|à|no|na|a)\s+(.+?)\s*,\s+.+?,?\s+que acontecer",
        intro, re.IGNORECASE,
    )
    return m[1].strip() if m else None


def extract_location(text: str) -> str | None:
    """'na cidade de Maceió (AL)' → 'Maceió/AL'."""
    m = re.search(r"na cidade d[eoa]s?\s+([A-ZÀ-Ý][^,.;]+?)(?:\s*[,.;]|\s+no período)", text, re.IGNORECASE)
    if not m:
        return None
    return re.sub(r"\s*\((\w{2})\)", r"/\1", m[1].strip())


def extract_event_dates(text: str) -> str | None:
    """Período do evento ('11 a 13 de junho de 2026') ou data única."""
    m = re.search(
        r"\d{1,2}(?:º)?(?:\s+de\s+[a-zç]+)?\s+(?:a|e)\s+\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}"
        r"|\d{1,2}(?:º)?\s+de\s+[a-zç]+\s+de\s+\d{4}",
        text, re.IGNORECASE,
    )
    return m[0] if m else None


def extract_price(edital_text: str) -> str | None:
    """Item 10.1 do edital: 'O valor a ser pago pelo participante… R$ X'."""
    m = re.search(
        r"valor a ser pago pelo participante.{0,60}?R\s*\$\s*([\d.]+,\d{2})",
        edital_text, re.IGNORECASE,
    )
    return f"R$ {m[1]}" if m else None
