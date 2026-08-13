from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import require_moderation_staff
from bot.services.embeds import RobloxEmbedFactory

if TYPE_CHECKING:
    from bot.app import RobloxBot


class JournalCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    @app_commands.command(name="журнал", description="Последние наказания на сервере")
    @app_commands.describe(
        количество="Сколько записей показать (3–20)",
        включая_отозванные="Показывать отозванные наказания",
    )
    async def journal(
        self,
        interaction: discord.Interaction,
        количество: app_commands.Range[int, 3, 20] = 10,
        включая_отозванные: bool = False,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await require_moderation_staff(interaction, self.bot.settings):
            return
        await interaction.response.defer()
        rows = await self.bot.db.recent_punishments(
            interaction.guild.id,
            limit=количество,
            include_revoked=включая_отозванные,
        )
        embed = RobloxEmbedFactory.journal_embed(rows, guild_name=interaction.guild.name)
        await interaction.followup.send(embed=embed)


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(JournalCog(bot))
