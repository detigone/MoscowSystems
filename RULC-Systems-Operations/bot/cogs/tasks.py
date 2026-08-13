from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

_ERLC_CONCURRENCY = 3


class BackgroundTasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.collect_erlc_stats.start()
        self.update_voice_counters.start()
        self.ticket_maintenance.start()

    async def cog_unload(self) -> None:
        self.collect_erlc_stats.cancel()
        self.update_voice_counters.cancel()
        self.ticket_maintenance.cancel()

    @tasks.loop(minutes=2)
    async def collect_erlc_stats(self) -> None:
        guild_ids = await self.bot.db.list_erlc_guilds()
        sem = asyncio.Semaphore(_ERLC_CONCURRENCY)

        async def _one(gid: int) -> None:
            async with sem:
                try:
                    await self.bot.erlc_stats.collect_guild(gid)
                except Exception:
                    logger.exception("Stats collection failed for guild %s", gid)

        await asyncio.gather(*[_one(gid) for gid in guild_ids])

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

    @tasks.loop(minutes=10)
    async def ticket_maintenance(self) -> None:
        if not hasattr(self.bot, "ticket_automation"):
            return
        guild_ids = set(await self.bot.db.guilds_with_open_tickets())
        guild_ids.update(g.id for g in self.bot.guilds)
        summary_idle = 0
        summary_orphans = 0
        summary_reminders = 0
        for guild_id in guild_ids:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            try:
                report = await self.bot.ticket_automation.run_guild_maintenance(guild)
                summary_idle += report.idle_closed
                summary_orphans += report.orphans_closed
                summary_reminders += report.reminders_sent
            except Exception:
                logger.exception("Ticket maintenance failed for guild %s", guild_id)
        if summary_idle or summary_orphans or summary_reminders:
            logger.info(
                "Ticket maintenance: orphans=%s idle_closed=%s reminders=%s",
                summary_orphans,
                summary_idle,
                summary_reminders,
            )

    @ticket_maintenance.before_loop
    async def before_ticket_maintenance(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BackgroundTasksCog(bot))
