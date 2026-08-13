from __future__ import annotations

import discord

from bot.settings import Settings


def is_guild_admin(member: discord.Member | discord.User, settings: Settings) -> bool:
    if settings.admin_discord_ids and member.id in settings.admin_discord_ids:
        return True
    if isinstance(member, discord.Member):
        return member.guild_permissions.manage_guild
    return False


def is_moderation_staff(member: discord.Member | discord.User, settings: Settings) -> bool:
    if is_guild_admin(member, settings):
        return True
    if isinstance(member, discord.Member):
        perms = member.guild_permissions
        return bool(perms.moderate_members or perms.kick_members or perms.ban_members)
    return False


async def require_moderation_staff(
    interaction: discord.Interaction,
    settings: Settings,
    *,
    ephemeral: bool = True,
) -> bool:
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        msg = "Только на сервере."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
        return False
    if not is_moderation_staff(interaction.user, settings):
        msg = "Только для staff."
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(msg, ephemeral=ephemeral)
        return False
    return True
