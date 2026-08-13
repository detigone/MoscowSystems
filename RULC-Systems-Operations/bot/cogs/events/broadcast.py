from __future__ import annotations

import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class BroadcastEventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild:
            return

        try:
            results = await self.bot.broadcast.relay_message(message)
            if results:
                logger.info(
                    "Broadcast from #%s (%s): %s",
                    message.channel.name,
                    message.guild.name,
                    "; ".join(results),
                )
        except Exception:
            logger.exception("Broadcast relay failed")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BroadcastEventsCog(bot))
