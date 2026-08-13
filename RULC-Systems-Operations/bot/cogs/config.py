from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import config_user_check
from bot.ui.config_panel import open_config_panel

logger = logging.getLogger(__name__)


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="config", description="Панель управления ботом")
    async def config(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not await config_user_check(interaction):
            return
        await open_config_panel(interaction, self.bot)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigCog(bot))
