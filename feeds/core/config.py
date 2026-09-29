"""Configuração via variáveis de ambiente e arquivo .env."""

from __future__ import annotations

import os
from pathlib import Path


class ConfigError(RuntimeError):
    """Configuração ausente ou inválida (ex.: webhook não definido)."""


def load_dotenv(path: Path) -> None:
    """Carrega KEY=valor do .env sem sobrescrever variáveis já definidas (ex.: secrets do Actions)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Defina a variável de ambiente {name} (no .env ou nos secrets do Actions).")
    return value
