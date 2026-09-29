"""Infraestrutura comum a todas as integrações."""

from feeds.core.config import ConfigError, load_dotenv
from feeds.core.discord import DiscordWebhook
from feeds.core.http import HttpClient
from feeds.core.integration import Integration
from feeds.core.state import SeenStore

__all__ = ["ConfigError", "DiscordWebhook", "HttpClient", "Integration", "SeenStore", "load_dotenv"]
