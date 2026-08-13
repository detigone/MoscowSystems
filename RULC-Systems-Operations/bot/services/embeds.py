from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import discord

from bot.db import Database

MEDALS = ("🥇", "🥈", "🥉")
TEAM_EMOJI = {
    "police": "🚓",
    "sheriff": "⭐",
    "dot": "🚧",
    "fire": "🚒",
    "ems": "🚑",
    "civ": "👤",
    "civilian": "👤",
}


@dataclass(frozen=True)
class EmbedTheme:
    guild_id: int
    brand_name: str
    footer_text: str
    thumbnail_url: str | None
    color_primary: int
    color_success: int
    color_warning: int
    color_danger: int
    color_info: int
    show_timestamp: bool
    use_guild_icon: bool
    players_per_field: int

    @classmethod
    def from_row(cls, row) -> EmbedTheme:
        return cls(
            guild_id=row["guild_id"],
            brand_name=row["brand_name"],
            footer_text=row["footer_text"],
            thumbnail_url=row["thumbnail_url"],
            color_primary=_hex_color(row["color_primary"]),
            color_success=_hex_color(row["color_success"]),
            color_warning=_hex_color(row["color_warning"]),
            color_danger=_hex_color(row["color_danger"]),
            color_info=_hex_color(row["color_info"]),
            show_timestamp=bool(row["show_timestamp"]),
            use_guild_icon=bool(row["use_guild_icon"]),
            players_per_field=max(5, min(int(row["players_per_field"]), 15)),
        )


def _hex_color(value: str) -> int:
    cleaned = (value or "#5865F2").lstrip("#")
    try:
        return int(cleaned, 16)
    except ValueError:
        return 0x5865F2


class EmbedFactory:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def theme(self, guild_id: int) -> EmbedTheme:
        row = await self.db.get_embed_settings(guild_id)
        return EmbedTheme.from_row(row)

    def _base(
        self,
        theme: EmbedTheme,
        guild: discord.Guild | None,
        *,
        title: str,
        color: int,
        description: str | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if theme.show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        icon = theme.thumbnail_url
        if not icon and theme.use_guild_icon and guild and guild.icon:
            icon = guild.icon.url
        if icon:
            embed.set_thumbnail(url=icon)
        footer = theme.footer_text
        if guild:
            footer = f"{footer} • {guild.name}"
        embed.set_footer(text=footer)
        return embed

    @staticmethod
    def _rank_label(rank: int) -> str:
        if 1 <= rank <= 3:
            return MEDALS[rank - 1]
        return f"`{rank:02d}`"

    @staticmethod
    def _leaderboard_lines(
        rows: list[tuple[str, int]],
        *,
        start: int = 1,
        suffix: str = "",
    ) -> list[str]:
        lines: list[str] = []
        for offset, (name, count) in enumerate(rows):
            rank = start + offset
            label = EmbedFactory._rank_label(rank)
            tail = f" {suffix}" if suffix else ""
            lines.append(f"{label} **{name}** — `{count}`{tail}")
        return lines

    @staticmethod
    def _team_icon(team: str) -> str:
        key = team.lower().strip()
        for name, emoji in TEAM_EMOJI.items():
            if name in key:
                return emoji
        return "▫️"

    async def players_embed(
        self,
        guild: discord.Guild,
        players: list,
        server_info: dict | None = None,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        info = server_info or {}
        online = info.get("players", len(players))
        max_players = info.get("max_players", "?")
        server_name = info.get("name", "ER:LC Server")

        embed = self._base(
            theme,
            guild,
            title="👥 Игроки на сервере",
            color=theme.color_primary,
            description=f"**{server_name}**\nОнлайн: **{online}** / **{max_players}**",
        )

        if not players:
            embed.add_field(
                name="📭 Пусто",
                value="На сервере сейчас нет игроков или сервер недоступен.",
                inline=False,
            )
            return embed

        by_team: dict[str, list[str]] = {}
        for player in players:
            team = getattr(player, "team", None) or "Без команды"
            icon = self._team_icon(team)
            by_team.setdefault(team, []).append(f"{icon} {player.name}")

        for team_name in sorted(by_team.keys(), key=str.lower):
            members = by_team[team_name]
            chunks = [
                members[i : i + theme.players_per_field]
                for i in range(0, len(members), theme.players_per_field)
            ]
            for idx, chunk in enumerate(chunks):
                field_title = f"{self._team_icon(team_name)} {team_name}"
                if len(chunks) > 1:
                    field_title += f" ({idx + 1}/{len(chunks)})"
                embed.add_field(name=field_title, value="\n".join(chunk)[:1024], inline=True)

        return embed

    async def ranking_embed(
        self,
        guild: discord.Guild,
        *,
        title: str,
        emoji: str,
        color_key: str,
        rows: list[tuple[str, int]],
        suffix: str = "",
        empty: str = "Нет данных за последние **24 часа**.\nБот собирает логи каждые 2 минуты.",
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        color = getattr(theme, f"color_{color_key}", theme.color_primary)
        embed = self._base(
            theme,
            guild,
            title=f"{emoji} {title}",
            color=color,
            description="Топ за последние **24 часа**",
        )
        if not rows:
            embed.add_field(name="📊 Данные", value=empty, inline=False)
            return embed

        top = rows[:5]
        rest = rows[5:10]
        embed.add_field(
            name="🏆 Топ-5",
            value="\n".join(self._leaderboard_lines(top, suffix=suffix))[:1024],
            inline=False,
        )
        if rest:
            embed.add_field(
                name="📋 Места 6–10",
                value="\n".join(self._leaderboard_lines(rest, start=6, suffix=suffix))[:1024],
                inline=False,
            )
        return embed

    async def activity_embed(
        self,
        guild: discord.Guild,
        scores: list[tuple[str, int]],
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        embed = self._base(
            theme,
            guild,
            title="📈 Рейтинг активности",
            color=theme.color_warning,
            description=(
                "Очки за **24 часа**:\n"
                "• Вход — **+2**\n"
                "• Выход, kill, команда — **+1**"
            ),
        )
        if not scores:
            embed.add_field(
                name="📊 Данные",
                value="Недостаточно активности за последние 24 часа.",
                inline=False,
            )
            return embed
        embed.add_field(
            name="🏆 Топ игроков",
            value="\n".join(
                f"{self._rank_label(i)} **{name}** — `{score}` очков"
                for i, (name, score) in enumerate(scores[:10], start=1)
            )[:1024],
            inline=False,
        )
        return embed

    async def command_ranking_embed(
        self,
        guild: discord.Guild,
        rows: list[tuple[str, int]],
    ) -> discord.Embed:
        formatted = [(f"`{cmd}`", cnt) for cmd, cnt in rows]
        return await self.ranking_embed(
            guild,
            title="Рейтинг команд",
            emoji="⌨️",
            color_key="info",
            rows=formatted,
            suffix="исп.",
        )

    async def status_embed(
        self,
        guild: discord.Guild,
        *,
        autorole: bool,
        erlc_name: str | None,
        voice_channel: int | None,
        sync_groups: int,
        broadcasts: int,
        rules: int,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        embed = self._base(
            theme,
            guild,
            title="⚙️ Настройки сервера",
            color=theme.color_primary,
            description=f"Конфигурация **{theme.brand_name}**",
        )
        embed.add_field(name="Autorole", value="✅ Включён" if autorole else "—", inline=True)
        embed.add_field(name="ER:LC", value=erlc_name or "—", inline=True)
        embed.add_field(
            name="Voice counter",
            value=f"<#{voice_channel}>" if voice_channel else "—",
            inline=True,
        )
        embed.add_field(name="Sync groups", value=str(sync_groups), inline=True)
        embed.add_field(name="Broadcasts", value=str(broadcasts), inline=True)
        embed.add_field(name="Conditional rules", value=str(rules), inline=True)
        return embed

    async def settings_preview_embed(self, guild: discord.Guild) -> discord.Embed:
        theme = await self.theme(guild.id)
        embed = self._base(
            theme,
            guild,
            title="🎨 Превью embed",
            color=theme.color_primary,
            description="Так будут выглядеть сообщения бота на этом сервере.",
        )
        embed.add_field(name="Primary", value=f"`#{theme.color_primary:06X}`", inline=True)
        embed.add_field(name="Success", value=f"`#{theme.color_success:06X}`", inline=True)
        embed.add_field(name="Warning", value=f"`#{theme.color_warning:06X}`", inline=True)
        embed.add_field(name="Danger", value=f"`#{theme.color_danger:06X}`", inline=True)
        embed.add_field(name="Info", value=f"`#{theme.color_info:06X}`", inline=True)
        embed.add_field(name="Brand", value=theme.brand_name, inline=True)
        embed.add_field(name="Footer", value=theme.footer_text, inline=False)
        embed.add_field(
            name="Опции",
            value=(
                f"Timestamp: **{'да' if theme.show_timestamp else 'нет'}**\n"
                f"Иконка сервера: **{'да' if theme.use_guild_icon else 'нет'}**\n"
                f"Игроков в поле: **{theme.players_per_field}**"
            ),
            inline=False,
        )
        return embed

    async def chart_colors(self, guild_id: int) -> dict[str, str]:
        theme = await self.theme(guild_id)
        return {
            "bg": "#2B2D31",
            "accent": f"#{theme.color_primary:06X}",
            "success": f"#{theme.color_success:06X}",
            "grid": "#404249",
            "text": "#FFFFFF",
        }

    async def broadcast_payload(
        self,
        guild: discord.Guild,
        *,
        author_name: str,
        author_icon: str | None,
        channel_name: str,
        content: str,
        image_url: str | None = None,
        attachment_urls: list[str] | None = None,
    ) -> dict:
        theme = await self.theme(guild.id)
        embed = discord.Embed(
            title=f"📢 {theme.brand_name}",
            description=content or "*(без текста)*",
            color=theme.color_primary,
        )
        if theme.show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        embed.set_author(name=author_name, icon_url=author_icon)
        embed.add_field(name="📍 Канал", value=f"#{channel_name}", inline=True)
        embed.add_field(name="🏛️ Сервер", value=guild.name, inline=True)
        embed.set_footer(text=theme.footer_text)
        thumb = theme.thumbnail_url
        if not thumb and theme.use_guild_icon and guild.icon:
            thumb = guild.icon.url
        if thumb:
            embed.set_thumbnail(url=thumb)
        if image_url:
            embed.set_image(url=image_url)
        elif attachment_urls:
            embed.add_field(
                name="📎 Вложения",
                value="\n".join(attachment_urls[:5])[:1024],
                inline=False,
            )
        return {
            "username": theme.brand_name,
            "avatar_url": guild.icon.url if guild.icon else None,
            "embeds": [embed.to_dict()],
            "allowed_mentions": {"parse": []},
        }
