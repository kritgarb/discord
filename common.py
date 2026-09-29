"""Utilitários compartilhados pelas integrações: .env, HTTP, estado e webhook do Discord."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "Mozilla/5.0 (compatible; discord-feeds/1.0)"


def load_dotenv(path=Path(__file__).with_name(".env")):
    """Carrega KEY=valor do .env sem sobrescrever variáveis já definidas (ex.: secrets do Actions)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def load_state(path):
    """Conjunto de IDs já enviados, ou None se o arquivo ainda não existe (primeira execução)."""
    if path.exists():
        return set(json.loads(path.read_text(encoding="utf-8")))
    return None


def save_state(path, posted):
    path.write_text(json.dumps(sorted(posted), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def send_webhook(webhook_url, payload):
    """Envia a mensagem ao webhook, respeitando o rate limit (429) do Discord."""
    data = json.dumps(payload).encode("utf-8")
    for _ in range(5):
        req = urllib.request.Request(
            webhook_url, data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            urllib.request.urlopen(req, timeout=30).close()
            return
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            retry_after = json.loads(e.read() or b"{}").get("retry_after", 2)
            time.sleep(float(retry_after) + 0.5)
    raise RuntimeError("Rate limit persistente do Discord")
