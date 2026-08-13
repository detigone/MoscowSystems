from __future__ import annotations

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def is_config_user(bot: commands.Bot, user_id: int) -> bool:
    return user_id in bot.settings.config_discord_ids


async def config_user_check(interaction: discord.Interaction) -> bool:
    bot = interaction.client
    if not isinstance(bot, commands.Bot):
        return False
    if not bot.settings.config_discord_ids:
        await interaction.response.send_message(
            "CONFIG_DISCORD_IDS не задан в .env — доступ к /config закрыт.",
            ephemeral=True,
        )
        return False
    if not is_config_user(bot, interaction.user.id):
        await interaction.response.send_message("Нет доступа к /config.", ephemeral=True)
        return False
    return True
