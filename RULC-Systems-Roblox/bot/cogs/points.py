from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.helpers import nickname_autocomplete
from bot.core.checks import require_moderation_staff
from bot.services.embeds import RobloxEmbedFactory
from bot.services.roblox_api import fetch_roblox_user

if TYPE_CHECKING:
    from bot.app import RobloxBot

logger = logging.getLogger(__name__)


class PointsCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    async def nickname_ac(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await nickname_autocomplete(interaction, current, self.bot)

    async def _resolve_player(
        self, guild_id: int, nickname: str
    ) -> tuple[dict | None, int, list]:
        if not self.bot.http_session:
            return None, 0, []
        roblox = await fetch_roblox_user(self.bot.http_session, nickname.strip())
        if not roblox:
            return None, 0, []
        rid = int(roblox["id"])
        points = await self.bot.db.sum_points(guild_id, rid)
        breakdown = await self.bot.db.punishment_breakdown(guild_id, rid)
        return roblox, points, breakdown

    @app_commands.command(name="баллы", description="Быстрая карточка баллов игрока")
    @app_commands.describe(никнейм="Roblox никнейм")
    @app_commands.autocomplete(никнейм=nickname_ac)
    async def points(self, interaction: discord.Interaction, никнейм: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.defer()
        roblox, total, breakdown = await self._resolve_player(interaction.guild.id, никнейм)
        if not roblox:
            await interaction.followup.send(f"Игрок **`{никнейм}`** не найден.", ephemeral=True)
            return
        embed = RobloxEmbedFactory.points_card(
            roblox,
            total_points=total,
            breakdown=breakdown,
            guild_name=interaction.guild.name,
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="риск", description="Оценка уровня риска игрока по баллам")
    @app_commands.describe(никнейм="Roblox никнейм")
    @app_commands.autocomplete(никнейм=nickname_ac)
    async def risk(self, interaction: discord.Interaction, никнейм: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.defer()
        roblox, total, breakdown = await self._resolve_player(interaction.guild.id, никнейм)
        if not roblox:
            await interaction.followup.send(f"Игрок **`{никнейм}`** не найден.", ephemeral=True)
            return
        embed = RobloxEmbedFactory.risk_embed(
            roblox,
            total_points=total,
            breakdown=breakdown,
            guild_name=interaction.guild.name,
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="топ", description="Топ игроков по активным баллам")
    @app_commands.describe(лимит="Сколько игроков показать (1–25)")
    async def top(
        self, interaction: discord.Interaction, лимит: app_commands.Range[int, 1, 25] = 10
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()
        rows = await self.bot.db.leaderboard(interaction.guild.id, limit=лимит)
        embed = RobloxEmbedFactory.leaderboard_embed(rows, guild_name=interaction.guild.name)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="радар", description="Игроки с высоким количеством баллов")
    @app_commands.describe(порог="Минимум баллов для попадания в радар (1–50)")
    async def radar(
        self,
        interaction: discord.Interaction,
        порог: app_commands.Range[int, 1, 50] = 5,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()
        rows = await self.bot.db.radar_players(interaction.guild.id, min_points=порог)
        embed = RobloxEmbedFactory.radar_embed(
            rows, threshold=порог, guild_name=interaction.guild.name
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="сравнить", description="Сравнить баллы двух игроков")
    @app_commands.describe(
        игрок_1="Первый Roblox никнейм",
        игрок_2="Второй Roblox никнейм",
    )
    async def compare(
        self,
        interaction: discord.Interaction,
        игрок_1: str,
        игрок_2: str,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.defer()
        if not self.bot.http_session:
            await interaction.followup.send("Бот ещё не готов.", ephemeral=True)
            return

        a = await fetch_roblox_user(self.bot.http_session, игрок_1.strip())
        b = await fetch_roblox_user(self.bot.http_session, игрок_2.strip())
        if not a or not b:
            missing = []
            if not a:
                missing.append(игрок_1)
            if not b:
                missing.append(игрок_2)
            await interaction.followup.send(
                f"Не найдены: {', '.join(f'`{n}`' for n in missing)}",
                ephemeral=True,
            )
            return

        gid = interaction.guild.id
        pa = await self.bot.db.sum_points(gid, int(a["id"]))
        pb = await self.bot.db.sum_points(gid, int(b["id"]))
        embed = RobloxEmbedFactory.compare_embed(a, pa, b, pb, guild_name=interaction.guild.name)
        await interaction.followup.send(embed=embed)


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(PointsCog(bot))
