"""Envio de mensagens para um webhook do Discord."""

from __future__ import annotations

import json
import time
import urllib.error

from feeds.core.http import HttpClient


class DiscordWebhook:
    MAX_RETRIES = 5

    def __init__(self, url: str, username: str, http: HttpClient):
        self.url = url
        self.username = username
        self.http = http

    def send_embed(self, embed: dict) -> None:
        self.send({
            "username": self.username,
            "embeds": [embed],
            "allowed_mentions": {"parse": []},  # nunca notifica ninguém
        })

    def send(self, payload: dict) -> None:
        """Envia o payload, esperando e tentando de novo quando o Discord devolve 429 (rate limit)."""
        for _ in range(self.MAX_RETRIES):
            try:
                self.http.post_json(self.url, payload)
                return
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                retry_after = json.loads(e.read() or b"{}").get("retry_after", 2)
                time.sleep(float(retry_after) + 0.5)
        raise RuntimeError("Rate limit persistente do Discord")
