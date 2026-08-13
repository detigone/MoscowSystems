from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.services.roblox_api import fetch_roblox_user, fetch_roblox_user_by_id

if TYPE_CHECKING:
    from bot.app import RobloxBot


def find_linked_member(guild: discord.Guild, roblox_name: str) -> discord.Member | None:
    needle = roblox_name.strip().lower()
    if not needle:
        return None
    for member in guild.members:
        if member.name.lower() == needle:
            return member
        if member.display_name.lower() == needle:
            return member
        if member.nick and member.nick.lower() == needle:
            return member
    return None


async def resolve_roblox_player(
    bot: RobloxBot,
    *,
    nickname: str | None = None,
    discord_user: discord.Member | discord.User | None = None,
    guild_id: int | None = None,
) -> dict | None:
    """Roblox-профиль по нику или Discord (через Bloxlink)."""
    if not bot.http_session:
        return None

    if discord_user and bot.bloxlink and bot.bloxlink.enabled:
        rid = await bot.bloxlink.discord_to_roblox(
            discord_user.id,
            guild_id=guild_id,
        )
        if rid:
            user = await fetch_roblox_user_by_id(bot.http_session, rid)
            if user:
                return user

    if nickname:
        return await fetch_roblox_user(bot.http_session, nickname.strip())
    return None


async def resolve_discord_for_roblox(
    bot: RobloxBot,
    guild: discord.Guild,
    roblox_id: int,
    roblox_name: str,
) -> tuple[discord.Member | None, str | None, int | None]:
    if bot.bloxlink and bot.bloxlink.enabled:
        member, source, offserver_id = await bot.bloxlink.resolve_guild_member(guild, roblox_id)
        if member or source == "bloxlink_offserver":
            return member, source, offserver_id

    member = find_linked_member(guild, roblox_name)
    if member:
        return member, "nickname", None
    return None, None, None
