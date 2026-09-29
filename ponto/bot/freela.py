"""Comandos dos freelas. Todas as respostas são privadas (só quem usou vê)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ponto.bot.ui import EMBED_COLOR, PERIOD_CHOICES, reply_error
from ponto.service import describe
from ponto.timeutil import format_duration, format_moment, period

if TYPE_CHECKING:
    from ponto.bot.client import PontoBot


class FreelaCog(commands.Cog):
    def __init__(self, bot: "PontoBot"):
        self.bot = bot
        self.clock = bot.clock

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await reply_error(interaction, error)

    async def _reply(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.send_message(text, ephemeral=True)

    @app_commands.command(name="entrar", description="Abre o seu ponto (começa a contar as horas).")
    @app_commands.guild_only()
    @app_commands.describe(nota="No que você vai trabalhar (opcional)")
    async def entrar(self, interaction: discord.Interaction, nota: str | None = None):
        s = self.clock.clock_in(interaction.guild_id, interaction.user.id, nota)
        await self._reply(interaction, f"Ponto aberto às {format_moment(s.started_at)}. Bom trabalho!")

    @app_commands.command(name="pausa", description="Pausa o seu ponto (o tempo em pausa não conta).")
    @app_commands.guild_only()
    async def pausa(self, interaction: discord.Interaction):
        s = self.clock.pause(interaction.guild_id, interaction.user.id)
        await self._reply(interaction, f"Ponto em pausa. Até agora: {format_duration(s.worked_seconds(self.clock.now()))}. "
                                       "Use /retomar para voltar.")

    @app_commands.command(name="retomar", description="Retoma o ponto depois de uma pausa.")
    @app_commands.guild_only()
    async def retomar(self, interaction: discord.Interaction):
        s = self.clock.resume(interaction.guild_id, interaction.user.id)
        await self._reply(interaction, f"Ponto retomado. Até agora: {format_duration(s.worked_seconds(self.clock.now()))}.")

    @app_commands.command(name="sair", description="Fecha o seu ponto.")
    @app_commands.guild_only()
    async def sair(self, interaction: discord.Interaction):
        s = self.clock.clock_out(interaction.guild_id, interaction.user.id)
        month = self.clock.totals(interaction.guild_id, period("mes", self.clock.now()), interaction.user.id)
        month_total = month[0].total_seconds if month else 0
        await self._reply(
            interaction,
            f"Ponto fechado: **{format_duration(s.worked_seconds(s.ended_at))}** "
            f"({format_moment(s.started_at)} → {format_moment(s.ended_at)}).\n"
            f"Total no mês: **{format_duration(month_total)}**.",
        )

    @app_commands.command(name="status", description="Mostra se o seu ponto está aberto e quanto já trabalhou.")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction):
        now = self.clock.now()
        s = self.clock.current(interaction.guild_id, interaction.user.id)
        today = self.clock.totals(interaction.guild_id, period("hoje", now), interaction.user.id)
        today_total = today[0].total_seconds if today else 0
        line = f"Seu ponto: {describe(s, now)}." if s else "Você está com o ponto fechado."
        await self._reply(interaction, f"{line}\nHoje (sessões encerradas): **{format_duration(today_total)}**.")

    @app_commands.command(name="horas", description="Suas horas num período.")
    @app_commands.guild_only()
    @app_commands.describe(periodo="Período (padrão: este mês)")
    @app_commands.choices(periodo=PERIOD_CHOICES)
    async def horas(self, interaction: discord.Interaction, periodo: app_commands.Choice[str] | None = None):
        p = period(periodo.value if periodo else "mes", self.clock.now())
        uid = interaction.user.id
        sessions = self.clock.sessions(interaction.guild_id, p, uid)
        adjustments = self.clock.adjustments(interaction.guild_id, p, uid)
        totals = self.clock.totals(interaction.guild_id, p, uid)
        total = totals[0].total_seconds if totals else 0

        lines = [f"`{format_moment(s.started_at)}` {format_duration(s.worked_seconds(s.ended_at))}"
                 + (f" · {s.note}" if s.note else "") for s in sessions[-20:]]
        if len(sessions) > 20:
            lines.insert(0, f"… e mais {len(sessions) - 20} sessões antes")
        lines += [f"`ajuste` {format_duration(a.seconds)} · {a.reason}" for a in adjustments]

        embed = discord.Embed(title=f"Suas horas · {p.label}", color=EMBED_COLOR,
                              description="\n".join(lines) or "Nenhum registro no período.")
        embed.add_field(name="Total", value=format_duration(total))
        embed.add_field(name="Sessões", value=str(len(sessions)))
        await interaction.response.send_message(embed=embed, ephemeral=True)
