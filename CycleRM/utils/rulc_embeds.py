"""RU:LC embed helpers for CycleRM — minimal style."""

from __future__ import annotations

import discord

from utils.constants import BLANK_COLOR, ERROR_COLOR


def finish_embed(
    embed: discord.Embed,
    *,
    guild_name: str | None = None,
    page: str | None = None,
) -> discord.Embed:
    if page:
        embed.set_footer(text=page)
    return embed


def panel_embed(
    title: str,
    description: str | None = None,
    *,
    color: int = BLANK_COLOR,
    guild_name: str | None = None,
) -> discord.Embed:
    return finish_embed(
        discord.Embed(title=title, description=description, color=color),
        guild_name=guild_name,
    )


def log_embed(title: str, *, guild_name: str | None = None) -> discord.Embed:
    return finish_embed(discord.Embed(title=title, color=BLANK_COLOR), guild_name=guild_name)


def error_embed(title: str, description: str, *, guild_name: str | None = None) -> discord.Embed:
    return finish_embed(
        discord.Embed(title=title, description=description, color=ERROR_COLOR),
        guild_name=guild_name,
    )
