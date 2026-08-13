from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from discord import app_commands

if TYPE_CHECKING:
    from bot.app import RobloxBot

logger = logging.getLogger(__name__)


async def nickname_autocomplete(
    interaction: app_commands.Interaction,
    current: str,
    bot: RobloxBot,
) -> list[app_commands.Choice[str]]:
    if not interaction.guild:
        return []
    gid = interaction.guild.id
    recent = await bot.db.recent_moderated_names(gid, 15)
    cached = await bot.db.search_names(gid, current, 15) if current else []

    seen: set[str] = set()
    merged: list[str] = []
    for name in recent + cached:
        key = name.lower()
        if key in seen:
            continue
        if current and current.lower() not in key:
            continue
        seen.add(key)
        merged.append(name)
        if len(merged) >= 25:
            break
    return [app_commands.Choice(name=n, value=n) for n in merged]


async def run_staff_command(
    interaction: app_commands.Interaction,
    action: Callable[[], Awaitable[None]],
    *,
    label: str = "command",
) -> None:
    try:
        await action()
    except Exception:
        logger.exception("Roblox /%s failed (guild %s)", label, interaction.guild_id)
        if interaction.response.is_done():
            await interaction.followup.send(
                "Не удалось выполнить команду. Попробуйте позже.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Не удалось выполнить команду. Попробуйте позже.",
                ephemeral=True,
            )
