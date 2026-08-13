from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import require_moderation_staff
from bot.services.embeds import RobloxEmbedFactory

if TYPE_CHECKING:
    from bot.app import RobloxBot


class StatsCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    @app_commands.command(name="статистика", description="Сводка модерации сервера")
    async def statistics(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()
        stats = await self.bot.db.guild_statistics(interaction.guild.id)
        embed = RobloxEmbedFactory.guild_stats_embed(stats, guild=interaction.guild)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="модератор", description="Статистика наказаний модератора")
    @app_commands.describe(участник="Discord-модератор")
    async def moderator(self, interaction: discord.Interaction, участник: discord.Member) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()
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

    @app_commands.command(name="staff-топ", description="Топ модераторов по выданным делам")
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
        rows = await self.bot.db.moderator_leaderboard(interaction.guild.id, limit=лимит)
        embed = RobloxEmbedFactory.moderator_top_embed(rows, guild_name=interaction.guild.name)
        await interaction.followup.send(embed=embed)


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(StatsCog(bot))
