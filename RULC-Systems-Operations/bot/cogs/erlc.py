from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

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

    async def _run_erlc(
        self,
        interaction: discord.Interaction,
        action: Callable[[discord.Interaction], Awaitable[None]],
    ) -> None:
        if not await self._need_erlc(interaction):
            return
        await interaction.response.defer()
        try:
            await action(interaction)
        except RuntimeError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
        except Exception:
            logger.exception("ER:LC command failed for guild %s", interaction.guild_id)
            await interaction.followup.send(
                "Ошибка ER:LC. Попробуйте позже.",
                ephemeral=True,
            )

    @erlc.command(name="игроки", description="Список игроков на сервере")
    async def erlc_players(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            embed = await self.bot.erlc_stats.build_players_embed(inter.guild)
            await inter.followup.send(embed=embed)

        await self._run_erlc(interaction, run)

    @rating.command(name="активности", description="Рейтинг активности игроков")
    async def rating_activity(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            embed = await self.bot.erlc_stats.activity_ranking(inter.guild)
            await inter.followup.send(embed=embed)

        await self._run_erlc(interaction, run)

    @rating.command(name="команд", description="Рейтинг команд по использованию")
    async def rating_commands(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            embed = await self.bot.erlc_stats.command_ranking_embed(inter.guild)
            await inter.followup.send(embed=embed)

        await self._run_erlc(interaction, run)

    @rating.command(name="смертей", description="Рейтинг смертей игроков")
    async def rating_deaths(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            embed = await self.bot.erlc_stats.build_ranking_embed(
                inter.guild,
                "Рейтинг смертей",
                "💀",
                "danger",
                "death",
            )
            await inter.followup.send(embed=embed)

        await self._run_erlc(interaction, run)

    @rating.command(name="убийств", description="Рейтинг убийств игроков")
    async def rating_kills(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            embed = await self.bot.erlc_stats.build_ranking_embed(
                inter.guild,
                "Рейтинг убийств",
                "🎯",
                "success",
                "kill",
            )
            await inter.followup.send(embed=embed)

        await self._run_erlc(interaction, run)

    @stats.command(name="игроков", description="График игроков за 24 часа")
    async def stats_players(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            chart = await self.bot.erlc_stats.chart_players_24h(inter.guild.id)
            if not chart:
                await inter.followup.send(
                    "Недостаточно данных. Подождите ~30 минут после запуска бота.",
                )
                return
            embed = await self.bot.erlc_stats.chart_embed(inter.guild, "Статистика игроков")
            await inter.followup.send(embed=embed, file=chart)

        await self._run_erlc(interaction, run)

    @stats.command(name="команд", description="График использования команд")
    async def stats_commands(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            chart = await self.bot.erlc_stats.chart_commands_24h(inter.guild.id)
            if not chart:
                await inter.followup.send("Нет данных по командам за 24 часа.")
                return
            embed = await self.bot.erlc_stats.chart_embed(inter.guild, "Статистика команд")
            await inter.followup.send(embed=embed, file=chart)

        await self._run_erlc(interaction, run)

    @stats.command(name="машин", description="График спавна машин")
    async def stats_vehicles(self, interaction: discord.Interaction) -> None:
        async def run(inter: discord.Interaction) -> None:
            chart = await self.bot.erlc_stats.chart_vehicles_24h(inter.guild.id)
            if not chart:
                await inter.followup.send("Нет данных по машинам за 24 часа.")
                return
            embed = await self.bot.erlc_stats.chart_embed(inter.guild, "Статистика машин")
            await inter.followup.send(embed=embed, file=chart)

        await self._run_erlc(interaction, run)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ErlcCog(bot))
