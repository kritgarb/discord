"""Classe base das integrações: busca itens, filtra os já enviados e publica no Discord."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Callable, ClassVar, Generic, Iterable, TypeVar

from feeds.core.config import require_env
from feeds.core.discord import DiscordWebhook
from feeds.core.http import HttpClient
from feeds.core.state import SeenStore

T = TypeVar("T")


class Integration(ABC, Generic[T]):
    """Fluxo comum a todas as integrações.

    Subclasses definem os metadados (ClassVars) e implementam:
    fetch, keys, label, to_embed e summary. Podem sobrescrever enrich, bootstrap e skip_reason.
    """

    slug: ClassVar[str]          # nome usado na CLI e no arquivo de estado
    title: ClassVar[str]         # nome amigável para logs
    username: ClassVar[str]      # nome exibido no Discord
    webhook_env: ClassVar[str]   # variável de ambiente com a URL do webhook

    SEND_INTERVAL = 1.0  # segundos entre mensagens

    def __init__(self, http: HttpClient, state: SeenStore, log: Callable[[str], None] = print):
        self.http = http
        self.state = state
        self.log = log

    # ----- a implementar pelas subclasses -----

    @abstractmethod
    def fetch(self, *, full: bool, limit: int | None) -> list[T]:
        """Itens disponíveis, do mais antigo para o mais novo.

        full=True pede uma busca mais profunda (primeira execução ou teste);
        limit, quando informado, permite parar assim que houver itens suficientes.
        """

    @abstractmethod
    def keys(self, item: T) -> set[str]:
        """Identificadores do item; se qualquer um já estiver no estado, o item não é reenviado."""

    @abstractmethod
    def label(self, item: T) -> str:
        """Texto curto para logs."""

    @abstractmethod
    def to_embed(self, item: T) -> dict:
        """Embed do Discord para o item."""

    @abstractmethod
    def summary(self, item: T) -> list[str]:
        """Linhas exibidas no --dry-run."""

    # ----- ganchos opcionais -----

    def enrich(self, item: T) -> T:
        """Completa o item antes do envio (ex.: buscar detalhes). Só roda nos itens que serão enviados."""
        return item

    def bootstrap(self, items: list[T]) -> Iterable[T]:
        """Na primeira execução, itens a marcar como enviados sem postar. Padrão: nenhum (posta tudo)."""
        return ()

    def skip_reason(self, item: T) -> str | None:
        """Motivo para não postar um item novo (já enriquecido), ou None para postar.

        Itens ignorados são marcados como vistos, pra não serem reavaliados a cada execução.
        Não se aplica no modo --test.
        """
        return None

    def webhook(self) -> DiscordWebhook:
        return DiscordWebhook(require_env(self.webhook_env), self.username, self.http)

    # ----- fluxo -----

    def pending(self, test: int | None = None) -> list[T]:
        """Itens a enviar nesta execução (já enriquecidos)."""
        first_run = self.state.is_new
        items = self.fetch(full=first_run or bool(test), limit=test)

        if test:
            selected = items[-test:]
        else:
            if first_run:
                for item in self.bootstrap(items):
                    self.state.add(self.keys(item))
            selected = [it for it in items if not self.state.contains_any(self.keys(it))]

        self.log(f"[{self.title}] {len(items)} encontrados, {len(selected)} novos.")
        to_post = []
        for item in map(self.enrich, selected):
            reason = None if test else self.skip_reason(item)
            if reason:
                self.state.add(self.keys(item))
                self.log(f"[{self.title}] Ignorado ({reason}): {self.label(item)}")
            else:
                to_post.append(item)
        return to_post

    def run(self, *, dry_run: bool = False, test: int | None = None) -> None:
        """Executa a integração.

        dry_run: só mostra no log, não envia nem salva estado.
        test: envia os N itens mais recentes mesmo que já enviados, sem alterar o estado.
        """
        items = self.pending(test)

        if dry_run:
            for item in items:
                self.log("")
                for line in self.summary(item):
                    self.log(line)
            return

        if not items:
            if not test:
                self.state.save()  # pode haver itens ignorados marcados como vistos
            return

        webhook = self.webhook()
        try:
            for item in items:
                webhook.send_embed(self.to_embed(item))
                if not test:
                    self.state.add(self.keys(item))
                self.log(f"[{self.title}] Postado: {self.label(item)}")
                time.sleep(self.SEND_INTERVAL)
        finally:
            # salva mesmo se falhar no meio, pra não repetir o que já foi
            if not test:
                self.state.save()
