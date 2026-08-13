"""Shared embed helpers for RU:LC Systems bots."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

from rulc_theme.tokens import PALETTE


def hex_color(value: str | None, *, fallback: str = "#2B2D31") -> int:
    cleaned = (value or fallback).lstrip("#")
    try:
        return int(cleaned, 16)
    except ValueError:
        return PALETTE.neutral


def build_footer(
    product: str,
    *,
    guild_name: str | None = None,
    extra: str | None = None,
    base: str | None = None,
    minimal: bool = True,
) -> str | None:
    if minimal:
        return extra or None
    root = base or f"RU:LC Systems · {product}"
    parts = [root]
    if guild_name:
        parts.append(guild_name)
    if extra:
        parts.append(extra)
    return " · ".join(parts)


def apply_footer(embed: discord.Embed, text: str | None) -> discord.Embed:
    if text:
        embed.set_footer(text=text)
    return embed


def styled_embed(
    *,
    title: str | None = None,
    description: str | None = None,
    color: int | None = None,
    product: str = "Roblox",
    guild_name: str | None = None,
    footer_extra: str | None = None,
    footer_base: str | None = None,
    timestamp: bool = False,
    minimal: bool = True,
) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color if color is not None else PALETTE.neutral,
    )
    if timestamp:
        embed.timestamp = datetime.now(timezone.utc)
    footer = build_footer(
        product,
        guild_name=guild_name,
        extra=footer_extra,
        base=footer_base,
        minimal=minimal,
    )
    return apply_footer(embed, footer)


def section_embed(
    *,
    title: str,
    description: str,
    product: str,
    color: int | None = None,
    guild_name: str | None = None,
) -> discord.Embed:
    return styled_embed(
        title=title,
        description=description,
        color=color or PALETTE.neutral,
        product=product,
        guild_name=guild_name,
    )


def finish_minimal(embed: discord.Embed, *, page: str | None = None) -> discord.Embed:
    return apply_footer(embed, page)
