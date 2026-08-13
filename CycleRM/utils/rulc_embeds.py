"""RU:LC embed helpers for CycleRM — thin wrapper over shared/rulc_theme."""

from __future__ import annotations

import discord

from rulc_theme.embeds import finish_minimal, styled_embed
from rulc_theme.tokens import PALETTE

PRODUCT = "CycleRM"


def finish_embed(
    embed: discord.Embed,
    *,
    guild_name: str | None = None,
    page: str | None = None,
) -> discord.Embed:
    return finish_minimal(embed, page=page)


def panel_embed(
    title: str,
    description: str | None = None,
    *,
    color: int = PALETTE.neutral,
    guild_name: str | None = None,
) -> discord.Embed:
    return styled_embed(
        product=PRODUCT,
        title=title,
        description=description,
        color=color,
        guild_name=guild_name,
    )


def log_embed(title: str, *, guild_name: str | None = None) -> discord.Embed:
    return styled_embed(product=PRODUCT, title=title, color=PALETTE.neutral, guild_name=guild_name)


def error_embed(title: str, description: str, *, guild_name: str | None = None) -> discord.Embed:
    return styled_embed(
        product=PRODUCT,
        title=title,
        description=description,
        color=PALETTE.danger,
        guild_name=guild_name,
    )
