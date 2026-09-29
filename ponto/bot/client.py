"""Cliente do Discord: registra os comandos e roda o lembrete de ponto aberto."""

from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

from ponto.config import Settings
from ponto.service import TimeClock
from ponto.timeutil import format_duration, format_moment

log = logging.getLogger("ponto")


class PontoBot(commands.Bot):
    def __init__(self, settings: Settings, clock: TimeClock):
        # Só slash commands: nenhum intent privilegiado (conteúdo de mensagens, membros) é necessário.
        super().__init__(command_prefix=commands.when_mentioned, intents=discord.Intents.default())
        self.settings = settings
        self.clock = clock

    async def setup_hook(self) -> None:
        from ponto.bot.admin import AdminCog
        from ponto.bot.freela import FreelaCog

        await self.add_cog(FreelaCog(self))
        await self.add_cog(AdminCog(self))

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()  # global: pode levar até 1h para aparecer
        log.info("%d comandos sincronizados", len(synced))

        if self.settings.remind_after_hours > 0:
            self.remind_open_sessions.start()

    async def on_ready(self) -> None:
        log.info("Conectado como %s (%s)", self.user, self.user.id)

    async def display_name(self, guild: discord.Guild | None, user_id: int) -> str:
        """Nome para relatórios; funciona sem o intent de membros."""
        member = guild.get_member(user_id) if guild else None
        if member:
            return member.display_name
        try:
            user = self.get_user(user_id) or await self.fetch_user(user_id)
            return user.global_name or user.name
        except discord.HTTPException:
            return str(user_id)

    @tasks.loop(minutes=10)
    async def remind_open_sessions(self) -> None:
        after = int(self.settings.remind_after_hours * 3600)
        for session in self.clock.sessions_to_remind(after):
            now = self.clock.now()
            try:
                user = self.get_user(session.user_id) or await self.fetch_user(session.user_id)
                await user.send(
                    f"Seu ponto está aberto desde {format_moment(session.started_at)} "
                    f"({format_duration(session.worked_seconds(now))} trabalhadas). "
                    "Se já terminou, use /sair no servidor. Se esqueceu de sair antes, "
                    "peça a um admin para fechar no horário certo."
                )
            except discord.HTTPException:
                log.warning("Não consegui mandar DM para %s (DMs fechadas?)", session.user_id)
            self.clock.mark_reminded(session)  # só um lembrete por sessão, mesmo se a DM falhar

    @remind_open_sessions.before_loop
    async def _wait_ready(self) -> None:
        await self.wait_until_ready()
