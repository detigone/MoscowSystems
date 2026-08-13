from __future__ import annotations

import logging

import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)


class BackgroundTasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.collect_erlc_stats.start()
        self.update_voice_counters.start()

    async def cog_unload(self) -> None:
        self.collect_erlc_stats.cancel()
        self.update_voice_counters.cancel()

    @tasks.loop(minutes=2)
    async def collect_erlc_stats(self) -> None:
        for guild_id in await self.bot.db.list_erlc_guilds():
            try:
                await self.bot.erlc_stats.collect_guild(guild_id)
            except Exception:
                logger.exception("Stats collection failed for guild %s", guild_id)

    @collect_erlc_stats.before_loop
    async def before_collect(self) -> None:
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=45)
    async def update_voice_counters(self) -> None:
        for row in await self.bot.db.list_voice_counters():
            guild = self.bot.get_guild(row["guild_id"])
            if not guild:
                continue
            channel = guild.get_channel(row["channel_id"])
            if not isinstance(channel, discord.VoiceChannel):
                continue
            try:
                count = await self.bot.erlc.get_player_count(guild.id)
                if count is None:
                    continue
                new_name = row["name_template"].format(count=count)
                if channel.name != new_name:
                    await channel.edit(name=new_name[:100], reason="ER:LC player counter")
            except discord.Forbidden:
                logger.warning("No permission to rename VC on guild %s", guild.id)
            except Exception:
                logger.exception("Voice counter update failed for guild %s", guild.id)

    @update_voice_counters.before_loop
    async def before_voice(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BackgroundTasksCog(bot))
