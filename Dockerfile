# Bot de relógio de ponto (python -m ponto). As integrações de feeds rodam no GitHub Actions, não aqui.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PONTO_DB=/data/ponto.db

WORKDIR /app
COPY requirements-bot.txt .
RUN pip install --no-cache-dir -r requirements-bot.txt

# ponto usa utilitários de feeds.core (.env, fuso de Brasília)
COPY feeds/ feeds/
COPY ponto/ ponto/

RUN useradd --create-home --uid 1000 bot && mkdir -p /data && chown bot /data
USER bot
VOLUME ["/data"]

CMD ["python", "-m", "ponto"]
