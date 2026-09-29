"""Comandos de admin (/ponto-admin ...). Só aparecem para quem pode gerenciar o servidor."""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ponto.bot.ui import EMBED_COLOR, PERIOD_CHOICES, reply_error
from ponto.service import TimeClockError, describe
from ponto.timeutil import Period, format_duration, format_moment, parse_clock_time, parse_duration, period

if TYPE_CHECKING:
    from ponto.bot.client import PontoBot


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class AdminCog(commands.GroupCog, group_name="ponto-admin", group_description="Administração do ponto dos freelas"):
    def __init__(self, bot: "PontoBot"):
        super().__init__()
        self.bot = bot
        self.clock = bot.clock

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await reply_error(interaction, error)

    @app_commands.command(name="relatorio", description="Horas de todos (ou de um freela) no período, com CSV.")
    @app_commands.describe(periodo="Período (padrão: este mês)", freela="Filtrar por uma pessoa")
    @app_commands.choices(periodo=PERIOD_CHOICES)
    async def relatorio(self, interaction: discord.Interaction,
                        periodo: app_commands.Choice[str] | None = None, freela: discord.Member | None = None):
        await interaction.response.defer(ephemeral=True, thinking=True)  # buscar nomes pode demorar
        p = period(periodo.value if periodo else "mes", self.clock.now())
        uid = freela.id if freela else None
        totals = self.clock.totals(interaction.guild_id, p, uid)

        names = {t.user_id: await self.bot.display_name(interaction.guild, t.user_id) for t in totals}
        lines = [f"**{names[t.user_id]}** · {format_duration(t.total_seconds)}"
                 + (f" (ajustes: {format_duration(t.adjusted_seconds)})" if t.adjusted_seconds else "")
                 + f" · {t.sessions} {'sessão' if t.sessions == 1 else 'sessões'}" for t in totals]
        grand_total = sum(t.total_seconds for t in totals)

        embed = discord.Embed(title=f"Relatório de horas · {p.label}", color=EMBED_COLOR,
                              description="\n".join(lines) or "Nenhum registro no período.")
        embed.add_field(name="Total geral", value=format_duration(grand_total))
        last_day = p.end - timedelta(days=1)
        embed.set_footer(text=f"{p.start:%d/%m/%Y} a {last_day:%d/%m/%Y} · sessões contam pela data de entrada")

        csv_file = discord.File(io.BytesIO(self._csv(interaction.guild_id, p, uid, names).encode("utf-8-sig")),
                                filename=f"horas-{p.start:%Y-%m-%d}.csv")
        await interaction.followup.send(embed=embed, file=csv_file, ephemeral=True)

    def _csv(self, guild_id: int, p: Period, user_id: int | None, names: dict[int, str]) -> str:
        """Uma linha por sessão e por ajuste; abre direto no Excel/Sheets (separador ';')."""
        out = io.StringIO()
        w = csv.writer(out, delimiter=";")
        w.writerow(["freela", "tipo", "entrada", "saida", "horas", "minutos", "nota"])
        for s in self.clock.sessions(guild_id, p, user_id):
            minutes = s.worked_seconds(s.ended_at) // 60
            w.writerow([names.get(s.user_id, s.user_id), "sessao", format_moment(s.started_at),
                        format_moment(s.ended_at), f"{minutes / 60:.2f}".replace(".", ","), minutes, s.note or ""])
        for a in self.clock.adjustments(guild_id, p, user_id):
            minutes = int(a.seconds / 60)
            w.writerow([names.get(a.user_id, a.user_id), "ajuste", format_moment(a.created_at), "",
                        f"{minutes / 60:.2f}".replace(".", ","), minutes, a.reason])
        return out.getvalue()

    @app_commands.command(name="ajustar", description="Soma ou subtrai horas de um freela (ex.: 1h30, -0h45).")
    @app_commands.describe(freela="Quem recebe o ajuste", duracao="Ex.: 1h30, 45m, -0h15", motivo="Por que o ajuste")
    async def ajustar(self, interaction: discord.Interaction, freela: discord.Member, duracao: str, motivo: str):
        a = self.clock.adjust(interaction.guild_id, freela.id, parse_duration(duracao), motivo, interaction.user.id)
        await interaction.response.send_message(
            f"Ajuste de **{format_duration(a.seconds)}** para {freela.mention} registrado ({a.reason}).",
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="fechar", description="Fecha o ponto aberto de um freela num horário (quem esqueceu /sair).")
    @app_commands.describe(freela="Quem esqueceu o ponto aberto", horario="Horário de saída, HH:MM (padrão: agora)")
    async def fechar(self, interaction: discord.Interaction, freela: discord.Member, horario: str | None = None):
        if not self.clock.current(interaction.guild_id, freela.id):
            raise TimeClockError(f"{freela.display_name} não está com o ponto aberto.")
        at = parse_clock_time(horario, self.clock.now()) if horario else None
        s = self.clock.clock_out(interaction.guild_id, freela.id, at)
        await interaction.response.send_message(
            f"Ponto de {freela.mention} fechado às {format_moment(s.ended_at)}: "
            f"**{format_duration(s.worked_seconds(s.ended_at))}**.",
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )

    @app_commands.command(name="abertos", description="Quem está com o ponto aberto agora.")
    async def abertos(self, interaction: discord.Interaction):
        now = self.clock.now()
        sessions = self.clock.open_sessions(interaction.guild_id)
        lines = [f"<@{s.user_id}> · {describe(s, now)}" for s in sessions]
        await interaction.response.send_message(
            "\n".join(lines) or "Ninguém está com o ponto aberto.",
            ephemeral=True, allowed_mentions=discord.AllowedMentions.none(),
        )
