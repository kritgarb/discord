"""Cliente HTTP mínimo sobre a biblioteca padrão."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; discord-feeds/1.0)"


class HttpClient:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: float = 60):
        self.user_agent = user_agent
        self.timeout = timeout

    def get(self, url: str, params: dict | None = None) -> bytes:
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read()

    def get_text(self, url: str, params: dict | None = None) -> str:
        return self.get(url, params).decode("utf-8", "replace")

    def post_json(self, url: str, payload: dict) -> None:
        """POST com corpo JSON. Erros HTTP sobem como urllib.error.HTTPError."""
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "User-Agent": self.user_agent},
        )
        urllib.request.urlopen(req, timeout=self.timeout).close()
