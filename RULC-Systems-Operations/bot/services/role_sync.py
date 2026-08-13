from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import discord

from bot.db import Database

logger = logging.getLogger(__name__)


@dataclass
class RoleChange:
    role_id: int
    role_name: str
    added: bool


class RoleSyncService:
    """Synchronizes configured roles across Discord servers in sync groups."""

    def __init__(self, db: Database, bot: discord.Client) -> None:
        self.db = db
        self.bot = bot
        self._lock = asyncio.Lock()
        self._recent_bot_changes: dict[tuple[int, int], float] = {}

    def mark_bot_change(self, guild_id: int, user_id: int, ttl: float = 8.0) -> None:
        self._recent_bot_changes[(guild_id, user_id)] = time.monotonic() + ttl

    def is_recent_bot_change(self, guild_id: int, user_id: int) -> bool:
        expires = self._recent_bot_changes.get((guild_id, user_id))
        if not expires:
            return False
        if time.monotonic() > expires:
            self._recent_bot_changes.pop((guild_id, user_id), None)
            return False
        return True

    async def sync_member_roles(
        self,
        member: discord.Member,
        changes: list[RoleChange] | None = None,
    ) -> list[str]:
        async with self._lock:
            return await self._sync_member_roles(member, changes)

    async def _sync_member_roles(
        self,
        member: discord.Member,
        changes: list[RoleChange] | None,
    ) -> list[str]:
        groups = await self.db.get_groups_for_guild(member.guild.id)
        if not groups:
            return []

        messages: list[str] = []
        for group in groups:
            group_id = group["id"]
            synced_role_names = {name.lower() for name in await self.db.get_synced_roles(group_id)}
            if not synced_role_names:
                continue

            mappings = await self.db.get_role_mappings(group_id)
            guild_ids = await self.db.get_group_guilds(group_id)
            target_guild_ids = [gid for gid in guild_ids if gid != member.guild.id]

            if changes:
                relevant = [
                    change
                    for change in changes
                    if change.role_name.lower() in synced_role_names
                    or self._has_mapping_for_role(mappings, member.guild.id, change.role_id)
                ]
                if not relevant:
                    continue
            else:
                relevant = None

            for target_guild_id in target_guild_ids:
                target_guild = self.bot.get_guild(target_guild_id)
                if not target_guild:
                    continue

                target_member = target_guild.get_member(member.id)
                if not target_member:
                    try:
                        target_member = await target_guild.fetch_member(member.id)
                    except discord.NotFound:
                        messages.append(
                            f"Пользователь {member} не найден на сервере {target_guild.name}"
                        )
                        continue
                    except discord.HTTPException as exc:
                        messages.append(
                            f"Не удалось получить участника на {target_guild.name}: {exc}"
                        )
                        continue

                if relevant:
                    for change in relevant:
                        result = await self._apply_single_change(
                            member,
                            target_member,
                            change,
                            mappings,
                            synced_role_names,
                        )
                        if result:
                            messages.append(result)
                else:
                    result = await self._mirror_all_synced_roles(
                        member,
                        target_member,
                        mappings,
                        synced_role_names,
                    )
                    messages.extend(result)

        return messages

    def _has_mapping_for_role(
        self,
        mappings: list,
        source_guild_id: int,
        source_role_id: int,
    ) -> bool:
        return any(
            row["source_guild_id"] == source_guild_id and row["source_role_id"] == source_role_id
            for row in mappings
        )

    async def _apply_single_change(
        self,
        source_member: discord.Member,
        target_member: discord.Member,
        change: RoleChange,
        mappings: list,
        synced_role_names: set[str],
    ) -> str | None:
        target_role = self._resolve_target_role(
            source_member.guild.id,
            change.role_id,
            change.role_name,
            target_member.guild,
            mappings,
            synced_role_names,
        )
        if not target_role:
            return None

        has_role = target_role in target_member.roles
        if change.added and has_role:
            return None
        if not change.added and not has_role:
            return None

        try:
            self.mark_bot_change(target_member.guild.id, target_member.id)
            if change.added:
                await target_member.add_roles(target_role, reason="Role sync bot")
                action = "выдана"
            else:
                await target_member.remove_roles(target_role, reason="Role sync bot")
                action = "снята"
            return f"{target_role.name} {action} на {target_member.guild.name}"
        except discord.Forbidden:
            return f"Нет прав выдать {target_role.name} на {target_member.guild.name}"
        except discord.HTTPException as exc:
            return f"Ошибка синхронизации на {target_member.guild.name}: {exc}"

    async def _mirror_all_synced_roles(
        self,
        source_member: discord.Member,
        target_member: discord.Member,
        mappings: list,
        synced_role_names: set[str],
    ) -> list[str]:
        messages: list[str] = []
        source_roles = {
            role.name.lower(): role
            for role in source_member.roles
            if role.name.lower() in synced_role_names
        }

        for role_name_lower, source_role in source_roles.items():
            target_role = self._resolve_target_role(
                source_member.guild.id,
                source_role.id,
                source_role.name,
                target_member.guild,
                mappings,
                synced_role_names,
            )
            if target_role and target_role not in target_member.roles:
                try:
                    self.mark_bot_change(target_member.guild.id, target_member.id)
                    await target_member.add_roles(target_role, reason="Role sync bot (full sync)")
                    messages.append(f"{target_role.name} выдана на {target_member.guild.name}")
                except discord.Forbidden:
                    messages.append(
                        f"Нет прав выдать {target_role.name} на {target_member.guild.name}"
                    )
                except discord.HTTPException as exc:
                    messages.append(f"Ошибка на {target_member.guild.name}: {exc}")

        for role_name_lower in synced_role_names:
            if role_name_lower in source_roles:
                continue
            target_role = discord.utils.find(
                lambda r: r.name.lower() == role_name_lower,
                target_member.guild.roles,
            )
            if target_role and target_role in target_member.roles:
                try:
                    self.mark_bot_change(target_member.guild.id, target_member.id)
                    await target_member.remove_roles(
                        target_role,
                        reason="Role sync bot (full sync)",
                    )
                    messages.append(f"{target_role.name} снята на {target_member.guild.name}")
                except discord.Forbidden:
                    messages.append(
                        f"Нет прав снять {target_role.name} на {target_member.guild.name}"
                    )
                except discord.HTTPException as exc:
                    messages.append(f"Ошибка на {target_member.guild.name}: {exc}")

        return messages

    def _resolve_target_role(
        self,
        source_guild_id: int,
        source_role_id: int,
        source_role_name: str,
        target_guild: discord.Guild,
        mappings: list,
        synced_role_names: set[str],
    ) -> discord.Role | None:
        for row in mappings:
            if (
                row["source_guild_id"] == source_guild_id
                and row["source_role_id"] == source_role_id
                and row["target_guild_id"] == target_guild.id
            ):
                return target_guild.get_role(row["target_role_id"])

        if source_role_name.lower() not in synced_role_names:
            return None

        return discord.utils.find(
            lambda role: role.name.lower() == source_role_name.lower(),
            target_guild.roles,
        )
