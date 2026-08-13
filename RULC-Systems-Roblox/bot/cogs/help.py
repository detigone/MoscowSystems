from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.embeds import COLOR_EMBED, RobloxEmbedFactory
from rulc_theme.embeds import section_embed
from rulc_theme.tokens import PRODUCT_ROBLOX

if TYPE_CHECKING:
    from bot.app import RobloxBot


class HelpSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Игрок", value="player", description="Поиск, баллы, риск"),
            discord.SelectOption(label="Рейтинги", value="rankings", description="Топ, радар, журнал"),
            discord.SelectOption(label="Staff", value="staff", description="Статистика модераторов"),
            discord.SelectOption(label="Настройки", value="config", description="Правила баллов"),
        ]
        super().__init__(placeholder="Раздел", options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        pages = {
            "player": "`/поиск` `/баллы` `/риск` `/сравнить`",
            "rankings": "`/топ` `/радар` `/журнал` `/статистика`",
            "staff": "`/модератор` `/staff-топ`",
            "config": "`/правила` `/установить-баллы`",
        }
        embed = section_embed(
            title="Команды",
            description=pages.get(self.values[0], "—"),
            product=PRODUCT_ROBLOX,
            color=COLOR_EMBED,
        )
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=180)
        self.add_item(HelpSelect())


class HelpCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    @app_commands.command(name="команды", description="Справка по командам бота")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        embed = RobloxEmbedFactory.help_embed()
        await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=True)


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(HelpCog(bot))
