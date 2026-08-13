from __future__ import annotations

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class GuildEventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _register_guild(self, guild: discord.Guild) -> None:
        icon = str(guild.icon.url) if guild.icon else None
        await self.bot.db.upsert_guild_registry(guild.id, guild.name, icon)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        await self._register_guild(guild)
        try:
            result = await self.bot.autorole.apply_bot_autorole(guild, self.bot.user)
            if result:
                logger.info("Bot autorole on join %s: %s", guild.name, result)
        except Exception:
            logger.exception("Bot autorole failed for guild %s", guild.id)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            await self._register_guild(guild)
            if hasattr(self.bot, "tickets"):
                fixed = await self.bot.tickets.sync_orphan_tickets(guild)
                if fixed:
                    logger.info("Synced %s orphan tickets in %s", fixed, guild.name)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildEventsCog(bot))
