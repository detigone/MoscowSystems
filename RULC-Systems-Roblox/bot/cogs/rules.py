from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.checks import is_guild_admin
from bot.services.embeds import RobloxEmbedFactory, type_label

if TYPE_CHECKING:
    from bot.app import RobloxBot


class RulesCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    @app_commands.command(name="правила", description="Таблица баллов за типы наказаний")
    async def show_rules(self, interaction: discord.Interaction) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        await interaction.response.defer()
        rules = await self.bot.db.get_point_rules(interaction.guild.id)
        embed = RobloxEmbedFactory.rules_embed(rules, guild_name=interaction.guild.name)
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="установить-баллы",
        description="Изменить количество баллов за тип наказания (Manage Server)",
    )
    @app_commands.describe(
        тип="Тип наказания (warning, kick, ban, bolo, …)",
        баллы="Сколько баллов начислять (0–100)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def set_points(
        self,
        interaction: discord.Interaction,
        тип: str,
        баллы: app_commands.Range[int, 0, 100],
    ) -> None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return
        if not is_guild_admin(interaction.user, self.bot.settings):
            await interaction.response.send_message("Недостаточно прав.", ephemeral=True)
            return

        type_key = тип.strip().lower()
        await self.bot.db.set_point_rule(interaction.guild.id, type_key, баллы)
        label = type_label(type_key)
        await interaction.response.send_message(
            f"✅ **{label}** — теперь **`{баллы}`** баллов.\n"
            f"*Новые* наказания будут использовать это значение.",
            ephemeral=True,
        )


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(RulesCog(bot))
