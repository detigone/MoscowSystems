from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.helpers import nickname_autocomplete, run_staff_command
from bot.core.checks import require_moderation_staff
from bot.services.embeds import RobloxEmbedFactory
from bot.services.player_resolve import resolve_roblox_player

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
        roblox = await resolve_roblox_player(self.bot, nickname=nickname, guild_id=guild_id)
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
        try:
            roblox, total, breakdown = await self._resolve_player(interaction.guild.id, никнейм)
        except Exception:
            logger.exception("/баллы failed for %s", никнейм)
            await interaction.followup.send("Не удалось получить данные.", ephemeral=True)
            return
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
        try:
            roblox, total, breakdown = await self._resolve_player(interaction.guild.id, никнейм)
        except Exception:
            logger.exception("/риск failed for %s", никнейм)
            await interaction.followup.send("Не удалось получить данные.", ephemeral=True)
            return
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
    @app_commands.default_permissions(moderate_members=True)
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

        async def work() -> None:
            rows = await self.bot.db.leaderboard(interaction.guild.id, limit=лимит)
            embed = RobloxEmbedFactory.leaderboard_embed(rows, guild_name=interaction.guild.name)
            await interaction.followup.send(embed=embed)

        await run_staff_command(interaction, work, label="топ")

    @app_commands.command(name="радар", description="Игроки с высоким количеством баллов")
    @app_commands.default_permissions(moderate_members=True)
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

        async def work() -> None:
            rows = await self.bot.db.radar_players(interaction.guild.id, min_points=порог)
            embed = RobloxEmbedFactory.radar_embed(
                rows, threshold=порог, guild_name=interaction.guild.name
            )
            await interaction.followup.send(embed=embed)

        await run_staff_command(interaction, work, label="радар")

    @app_commands.command(name="сравнить", description="Сравнить баллы двух игроков")
    @app_commands.describe(
        игрок_1="Первый Roblox никнейм",
        игрок_2="Второй Roblox никнейм",
    )
    @app_commands.autocomplete(игрок_1=nickname_ac, игрок_2=nickname_ac)
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
        try:
            a = await resolve_roblox_player(self.bot, nickname=игрок_1.strip())
            b = await resolve_roblox_player(self.bot, nickname=игрок_2.strip())
            gid = interaction.guild.id
            pa = await self.bot.db.sum_points(gid, int(a["id"])) if a else 0
            pb = await self.bot.db.sum_points(gid, int(b["id"])) if b else 0
        except Exception:
            logger.exception("/сравнить failed")
            await interaction.followup.send("Не удалось получить данные.", ephemeral=True)
            return
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

        embed = RobloxEmbedFactory.compare_embed(a, pa, b, pb, guild_name=interaction.guild.name)
        await interaction.followup.send(embed=embed)


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(PointsCog(bot))
