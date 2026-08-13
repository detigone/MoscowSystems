from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.services.role_sync import RoleChange

logger = logging.getLogger(__name__)


class SyncEventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.roles != after.roles:
            if not self.bot.role_sync.is_recent_bot_change(after.guild.id, after.id):
                await self._handle_role_sync(before, after)

        if before.roles != after.roles:
            try:
                results = await self.bot.conditional_roles.evaluate_member(after)
                if results:
                    logger.info(
                        "Conditional roles for %s (%s): %s",
                        after,
                        after.guild.name,
                        "; ".join(results),
                    )
            except Exception:
                logger.exception("Conditional role evaluation failed for %s", after)

    async def _handle_role_sync(self, before: discord.Member, after: discord.Member) -> None:
        before_ids = {role.id for role in before.roles}
        after_ids = {role.id for role in after.roles}

        added_ids = after_ids - before_ids
        removed_ids = before_ids - after_ids

        changes: list[RoleChange] = []
        for role in after.roles:
            if role.id in added_ids:
                changes.append(RoleChange(role.id, role.name, added=True))
        for role in before.roles:
            if role.id in removed_ids:
                changes.append(RoleChange(role.id, role.name, added=False))

        if not changes:
            return

        try:
            results = await self.bot.role_sync.sync_member_roles(after, changes)
            if results:
                logger.info(
                    "Synced roles for %s (%s): %s",
                    after,
                    after.guild.name,
                    "; ".join(results),
                )
        except Exception:
            logger.exception("Role sync failed for %s", after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            autorole_result = await self.bot.autorole.apply_member_autorole(member)
            if autorole_result:
                logger.info("Autorole for %s (%s): %s", member, member.guild.name, autorole_result)
        except Exception:
            logger.exception("Member autorole failed for %s", member)

        try:
            results = await self.bot.role_sync.sync_member_roles(member)
            if results:
                logger.info(
                    "Initial sync for joined member %s (%s): %s",
                    member,
                    member.guild.name,
                    "; ".join(results),
                )
        except Exception:
            logger.exception("Initial role sync failed for %s", member)

        try:
            member = await member.guild.fetch_member(member.id)
            results = await self.bot.conditional_roles.evaluate_member(member)
            if results:
                logger.info(
                    "Conditional roles on join for %s (%s): %s",
                    member,
                    member.guild.name,
                    "; ".join(results),
                )
        except Exception:
            logger.exception("Conditional roles on join failed for %s", member)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SyncEventsCog(bot))
