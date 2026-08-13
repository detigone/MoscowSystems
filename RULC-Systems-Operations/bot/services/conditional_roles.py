from __future__ import annotations

import logging

import discord

from bot.db import Database

logger = logging.getLogger(__name__)


class ConditionalRoleService:
    """Выдаёт роль A, если у участника есть хотя бы одна роль из списка B."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def evaluate_member(self, member: discord.Member) -> list[str]:
        rules = await self.db.get_conditional_rules(member.guild.id)
        if not rules:
            return []

        member_role_ids = {role.id for role in member.roles}
        messages: list[str] = []

        for rule in rules:
            if not rule["enabled"]:
                continue

            trigger_ids = set(await self.db.get_conditional_triggers(rule["id"]))
            if not trigger_ids:
                continue

            target_role = member.guild.get_role(rule["target_role_id"])
            if not target_role:
                messages.append(f"Правило «{rule['name']}»: целевая роль не найдена")
                continue

            has_trigger = bool(member_role_ids & trigger_ids)
            has_target = target_role in member.roles

            if has_trigger and not has_target:
                try:
                    await member.add_roles(target_role, reason=f"Conditional: {rule['name']}")
                    messages.append(f"Выдана {target_role.name} (правило «{rule['name']}»)")
                except discord.Forbidden:
                    messages.append(f"Нет прав выдать {target_role.name}")
                except discord.HTTPException as exc:
                    messages.append(f"Ошибка правила «{rule['name']}»: {exc}")

            elif (
                not has_trigger
                and has_target
                and rule["remove_on_loss"]
            ):
                try:
                    await member.remove_roles(target_role, reason=f"Conditional remove: {rule['name']}")
                    messages.append(f"Снята {target_role.name} (правило «{rule['name']}»)")
                except discord.Forbidden:
                    messages.append(f"Нет прав снять {target_role.name}")
                except discord.HTTPException as exc:
                    messages.append(f"Ошибка снятия «{rule['name']}»: {exc}")

        return messages
