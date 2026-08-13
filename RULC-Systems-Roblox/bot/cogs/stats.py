from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.helpers import run_staff_command
from bot.core.checks import require_moderation_staff
from bot.services.embeds import RobloxEmbedFactory

if TYPE_CHECKING:
    from bot.app import RobloxBot


class StatsCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    @app_commands.command(name="статистика", description="Сводка модерации сервера")
    @app_commands.default_permissions(moderate_members=True)
    async def statistics(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()

        async def work() -> None:
            stats = await self.bot.db.guild_statistics(interaction.guild.id)
            embed = RobloxEmbedFactory.guild_stats_embed(stats, guild=interaction.guild)
            await interaction.followup.send(embed=embed)

        await run_staff_command(interaction, work, label="статистика")

    @app_commands.command(name="модератор", description="Статистика наказаний модератора")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(участник="Discord-модератор")
    async def moderator(self, interaction: discord.Interaction, участник: discord.Member) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()

        async def work() -> None:
            stats = await self.bot.db.moderator_stats(interaction.guild.id, участник.id)
            if not stats:
                await interaction.followup.send(
                    f"У {участник.mention} нет выданных наказаний в базе.",
                    ephemeral=True,
                )
                return
            embed = RobloxEmbedFactory.moderator_embed(
                участник, stats, guild_name=interaction.guild.name
            )
            await interaction.followup.send(embed=embed)

        await run_staff_command(interaction, work, label="модератор")

    @app_commands.command(name="staff-топ", description="Топ модераторов по выданным делам")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(лимит="Сколько показать (3–15)")
    async def staff_top(
        self, interaction: discord.Interaction, лимит: app_commands.Range[int, 3, 15] = 10
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()

        async def work() -> None:
            rows = await self.bot.db.moderator_leaderboard(interaction.guild.id, limit=лимит)
            embed = RobloxEmbedFactory.moderator_top_embed(
                rows, guild_name=interaction.guild.name
            )
            await interaction.followup.send(embed=embed)

        await run_staff_command(interaction, work, label="staff-топ")


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(StatsCog(bot))
