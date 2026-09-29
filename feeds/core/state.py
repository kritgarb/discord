"""Registro persistente do que já foi enviado ao Discord."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class SeenStore:
    """Conjunto de chaves (IDs, links…) já enviadas, salvo como lista JSON ordenada.

    O arquivo ainda não existir indica a primeira execução da integração.
    """

    def __init__(self, path: Path):
        self.path = path
        self.is_new = not path.exists()
        self._keys: set[str] = set() if self.is_new else set(json.loads(path.read_text(encoding="utf-8")))

    def __len__(self) -> int:
        return len(self._keys)

    def contains_any(self, keys: Iterable[str]) -> bool:
        return any(k in self._keys for k in keys)

    def add(self, keys: Iterable[str]) -> None:
        self._keys.update(keys)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._keys), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.is_new = False
