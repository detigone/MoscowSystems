from __future__ import annotations

import logging

import discord

from bot.db import Database

logger = logging.getLogger(__name__)


class AutoroleService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def apply_member_autorole(self, member: discord.Member) -> str | None:
        config = await self.db.get_guild_autoroles(member.guild.id)
        if not config or not config["member_enabled"] or not config["member_role_id"]:
            return None

        role = member.guild.get_role(config["member_role_id"])
        if not role:
            return f"Autorole: роль {config['member_role_id']} не найдена"

        if role in member.roles:
            return None

        try:
            await member.add_roles(role, reason="Autorole при входе")
            return f"Выдана autorole {role.name}"
        except discord.Forbidden:
            return f"Нет прав выдать autorole {role.name}"
        except discord.HTTPException as exc:
            return f"Ошибка autorole: {exc}"

    async def apply_bot_autorole(self, guild: discord.Guild, bot_user: discord.ClientUser) -> str | None:
        config = await self.db.get_guild_autoroles(guild.id)
        if not config or not config["bot_enabled"] or not config["bot_role_id"]:
            return None

        role = guild.get_role(config["bot_role_id"])
        if not role:
            return f"Bot autorole: роль {config['bot_role_id']} не найдена"

        member = guild.get_member(bot_user.id)
        if not member:
            try:
                member = await guild.fetch_member(bot_user.id)
            except discord.HTTPException:
                return "Bot autorole: не удалось получить участника бота"

        if role in member.roles:
            return None

        try:
            await member.add_roles(role, reason="Autorole для бота")
            return f"Боту выдана роль {role.name}"
        except discord.Forbidden:
            return f"Нет прав выдать боту роль {role.name}"
        except discord.HTTPException as exc:
            return f"Ошибка bot autorole: {exc}"
