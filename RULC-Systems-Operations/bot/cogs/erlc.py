from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class ErlcCog(commands.Cog):
    erlc = app_commands.Group(name="erlc", description="ER:LC — игроки, рейтинги и статистика")
    rating = app_commands.Group(name="рейтинг", description="Рейтинги за 24 часа", parent=erlc)
    stats = app_commands.Group(name="статистика", description="Графики за 24 часа", parent=erlc)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _need_erlc(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return False
        erlc = await self.bot.db.get_erlc_server(interaction.guild.id)
        if not erlc:
            await interaction.response.send_message(
                "ER:LC не настроен. Владелец: `/config` → раздел **ER:LC**",
                ephemeral=True,
            )
            return False
        return True

    @erlc.command(name="игроки", description="Список игроков на сервере")
    async def erlc_players(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        try:
            embed = await self.bot.erlc_stats.build_players_embed(interaction.guild)
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            await interaction.followup.send(f"Ошибка: {exc}")

    @rating.command(name="активности", description="Рейтинг активности игроков")
    async def rating_activity(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        embed = await self.bot.erlc_stats.activity_ranking(interaction.guild)
        await interaction.followup.send(embed=embed)

    @rating.command(name="команд", description="Рейтинг команд по использованию")
    async def rating_commands(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        embed = await self.bot.erlc_stats.command_ranking_embed(interaction.guild)
        await interaction.followup.send(embed=embed)

    @rating.command(name="смертей", description="Рейтинг смертей игроков")
    async def rating_deaths(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        embed = await self.bot.erlc_stats.build_ranking_embed(
            interaction.guild,
            "Рейтинг смертей",
            "💀",
            "danger",
            "death",
        )
        await interaction.followup.send(embed=embed)

    @rating.command(name="убийств", description="Рейтинг убийств игроков")
    async def rating_kills(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        embed = await self.bot.erlc_stats.build_ranking_embed(
            interaction.guild,
            "Рейтинг убийств",
            "🎯",
            "success",
            "kill",
        )
        await interaction.followup.send(embed=embed)

    @stats.command(name="игроков", description="График игроков за 24 часа")
    async def stats_players(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        chart = await self.bot.erlc_stats.chart_players_24h(interaction.guild.id)
        if not chart:
            await interaction.followup.send("Недостаточно данных. Подождите ~30 минут после запуска бота.")
            return
        embed = await self.bot.erlc_stats.chart_embed(interaction.guild, "Статистика игроков")
        await interaction.followup.send(embed=embed, file=chart)

    @stats.command(name="команд", description="График использования команд")
    async def stats_commands(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        chart = await self.bot.erlc_stats.chart_commands_24h(interaction.guild.id)
        if not chart:
            await interaction.followup.send("Нет данных по командам за 24 часа.")
            return
        embed = await self.bot.erlc_stats.chart_embed(interaction.guild, "Статистика команд")
        await interaction.followup.send(embed=embed, file=chart)

    @stats.command(name="машин", description="График спавна машин")
    async def stats_vehicles(self, interaction: discord.Interaction) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        chart = await self.bot.erlc_stats.chart_vehicles_24h(interaction.guild.id)
        if not chart:
            await interaction.followup.send("Нет данных по машинам за 24 часa.")
            return
        embed = await self.bot.erlc_stats.chart_embed(interaction.guild, "Статистика машин")
        await interaction.followup.send(embed=embed, file=chart)


async def setup(bot: commands.Bot) -> None:
    cog = ErlcCog(bot)
    await bot.add_cog(cog)
    bot.tree.add_command(cog.erlc)
