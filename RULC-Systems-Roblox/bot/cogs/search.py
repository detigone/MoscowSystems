from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.helpers import nickname_autocomplete
from bot.services.roblox_api import fetch_roblox_user
from bot.ui.search_view import SearchPaginationView

if TYPE_CHECKING:
    from bot.app import RobloxBot

logger = logging.getLogger(__name__)


class SearchCog(commands.Cog):
    def __init__(self, bot: RobloxBot) -> None:
        self.bot = bot

    async def nickname_ac(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await nickname_autocomplete(interaction, current, self.bot)

    @app_commands.command(
        name="поиск",
        description="Roblox профиль и наказания игрока",
    )
    @app_commands.describe(
        никнейм="Roblox никнейм игрока, у которого вы хотите просмотреть наказания.",
    )
    @app_commands.autocomplete(никнейм=nickname_ac)
    async def poisk(self, interaction: discord.Interaction, никнейм: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return

        await interaction.response.defer()

        query = никнейм.strip()
        if not self.bot.http_session:
            await interaction.followup.send("Бот ещё не готов. Попробуйте снова.", ephemeral=True)
            return

        try:
            roblox = await fetch_roblox_user(self.bot.http_session, query)
            if not roblox:
                await interaction.followup.send(
                    f"Игрок **`{query}`** не найден в Roblox.",
                    ephemeral=True,
                )
                return

            gid = interaction.guild.id
            rid = int(roblox["id"])
            total_points = await self.bot.db.sum_points(gid, rid)
            punishments = await self.bot.db.list_punishments(
                gid, rid, include_revoked=True
            )
        except Exception:
            logger.exception("/поиск failed for %s", query)
            await interaction.followup.send(
                "Не удалось получить данные. Попробуйте позже.",
                ephemeral=True,
            )
            return

        view = SearchPaginationView(
            self,
            guild_id=gid,
            guild_name=interaction.guild.name,
            roblox=roblox,
            punishments=punishments,
            total_points=total_points,
            author=interaction.user,
        )
        view._owner_id = interaction.user.id

        if view.total_pages <= 1:
            view.clear_items()

        await interaction.followup.send(
            embed=view.build_embed(),
            view=view if view.total_pages > 1 else None,
        )


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(SearchCog(bot))
