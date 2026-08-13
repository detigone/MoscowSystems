from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from bot.cogs.helpers import nickname_autocomplete
from bot.services.player_resolve import resolve_discord_for_roblox, resolve_roblox_player
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
        никнейм="Roblox никнейм (не нужен, если указан Discord)",
        discord="Discord-участник (через Bloxlink)",
    )
    @app_commands.autocomplete(никнейм=nickname_ac)
    async def poisk(
        self,
        interaction: discord.Interaction,
        никнейм: str | None = None,
        discord: discord.Member | None = None,
    ) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return

        await interaction.response.defer()

        query = (никнейм or "").strip()
        if not query and not discord:
            await interaction.followup.send(
                "Укажите **никнейм** или **Discord-участника**.",
                ephemeral=True,
            )
            return

        try:
            roblox = await resolve_roblox_player(
                self.bot,
                nickname=query or None,
                discord_user=discord,
                guild_id=interaction.guild.id,
            )
            if not roblox:
                label = query or (discord.display_name if discord else "?")
                await interaction.followup.send(
                    f"Игрок **`{label}`** не найден в Roblox.",
                    ephemeral=True,
                )
                return

            gid = interaction.guild.id
            rid = int(roblox["id"])
            total_points = await self.bot.db.sum_points(gid, rid)
            total_records = await self.bot.db.count_punishments(gid, rid, include_revoked=True)
            punishments = await self.bot.db.list_punishments(
                gid, rid, include_revoked=True, limit=100
            )
            truncated = total_records > len(punishments)
            discord_member, link_source, offserver_id = await resolve_discord_for_roblox(
                self.bot,
                interaction.guild,
                rid,
                str(roblox.get("name") or query),
            )
            if discord and not discord_member:
                discord_member = discord if isinstance(discord, discord.Member) else None
                if discord_member:
                    link_source = "bloxlink"
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
            roblox_id=rid,
            punishments=punishments,
            total_points=total_points,
            total_records=total_records,
            author=interaction.user,
            discord_member=discord_member,
            discord_link_source=link_source,
            discord_offserver_id=offserver_id,
            history_note=(
                f"Показаны последние {len(punishments)} из {total_records}"
                if truncated
                else None
            ),
        )
        view._owner_id = interaction.user.id

        await interaction.followup.send(embed=view.build_embed(), view=view)
        try:
            messages = await interaction.original_response()
            view.bind_message(messages)
        except discord.HTTPException:
            pass


async def setup(bot: RobloxBot) -> None:
    await bot.add_cog(SearchCog(bot))
