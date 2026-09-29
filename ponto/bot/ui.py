"""Peças compartilhadas pelos comandos: escolhas de período, cor e tratamento de erros."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from ponto.service import TimeClockError
from ponto.timeutil import PERIODS

log = logging.getLogger("ponto")

EMBED_COLOR = 0x2ECC71
PERIOD_CHOICES = [app_commands.Choice(name=label, value=key) for key, label in PERIODS.items()]


async def reply_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    """Responde em privado: erros de regra/entrada com a própria mensagem, o resto com uma mensagem genérica."""
    original = getattr(error, "original", error)
    if isinstance(original, (TimeClockError, ValueError)):
        message = str(original)
    elif isinstance(error, app_commands.MissingPermissions):
        message = "Esse comando é só para admins."
    else:
        log.error("Erro no comando %s", interaction.command and interaction.command.qualified_name,
                  exc_info=original)
        message = "Algo deu errado. Tente de novo; se continuar, avise um admin."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)
