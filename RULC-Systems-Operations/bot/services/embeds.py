from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import discord

from bot.db import Database
from rulc_theme.embeds import hex_color
from rulc_theme.tokens import HEX_PRIMARY

MEDALS = ()  # minimal: plain numbers
TEAM_EMOJI: dict[str, str] = {}


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
    return hex_color(value, fallback=HEX_PRIMARY)


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
        author: str | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        if author and guild:
            embed.set_author(name=author, icon_url=guild.icon.url if guild.icon else None)
        if theme.show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        icon = theme.thumbnail_url
        if not icon and theme.use_guild_icon and guild and guild.icon:
            icon = guild.icon.url
        if icon:
            embed.set_thumbnail(url=icon)
        if theme.footer_text:
            embed.set_footer(text=theme.footer_text)
        return embed

    @staticmethod
    def _rank_label(rank: int) -> str:
        return f"{rank}."

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
            lines.append(f"{label} **{name}** — {count}{tail}")
        return lines

    @staticmethod
    def _team_icon(team: str) -> str:
        return ""

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
            title="Игроки",
            color=theme.color_primary,
            description=f"{server_name} · {online}/{max_players}",
        )

        if not players:
            embed.description = (embed.description or "") + "\n\nСервер пуст."
            return embed

        by_team: dict[str, list[str]] = {}
        for player in players:
            team = getattr(player, "team", None) or "Без команды"
            by_team.setdefault(team, []).append(player.name)

        for team_name in sorted(by_team.keys(), key=str.lower):
            members = by_team[team_name]
            chunks = [
                members[i : i + theme.players_per_field]
                for i in range(0, len(members), theme.players_per_field)
            ]
            for idx, chunk in enumerate(chunks):
                field_title = team_name
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
        empty: str = "Нет данных за 24 часа.",
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        color = getattr(theme, f"color_{color_key}", theme.color_primary)
        embed = self._base(
            theme,
            guild,
            title=title,
            color=color,
        )
        if not rows:
            embed.description = empty
            return embed

        lines = self._leaderboard_lines(rows[:10], suffix=suffix)
        embed.description = "\n".join(lines)[:4096]
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
            title="Активность",
            color=theme.color_primary,
            description="Вход +2 · выход/kill/команда +1",
        )
        if not scores:
            embed.description = (embed.description or "") + "\n\nНедостаточно данных."
            return embed
        embed.description = "\n".join(
            f"{self._rank_label(i)} **{name}** — {score}"
            for i, (name, score) in enumerate(scores[:10], start=1)
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
            title="Команды",
            emoji="",
            color_key="info",
            rows=formatted,
            suffix="исп.",
        )

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
            title=theme.brand_name,
            description=f"#{channel_name} · {guild.name}\n\n{content or '—'}",
            color=theme.color_primary,
        )
        if theme.show_timestamp:
            embed.timestamp = datetime.now(timezone.utc)
        if theme.footer_text:
            embed.set_footer(text=theme.footer_text)
        if image_url:
            embed.set_image(url=image_url)
        elif attachment_urls:
            embed.description = (embed.description or "") + "\n\n" + "\n".join(attachment_urls[:5])[:500]
        return {
            "username": theme.brand_name,
            "avatar_url": guild.icon.url if guild.icon else None,
            "embeds": [embed.to_dict()],
            "allowed_mentions": {"parse": []},
        }

    async def ticket_panel_embed(self, guild: discord.Guild) -> discord.Embed:
        theme = await self.theme(guild.id)
        categories = await self.db.list_ticket_categories(guild.id)
        config = await self.db.get_ticket_config(guild.id)

        lines = [
            f"{c['emoji']} **{c['name']}**"
            + (f" — {c['description']}" if c.get("description") else "")
            for c in categories
            if int(c.get("enabled", 1))
        ]
        max_open = int(config["max_open_per_user"])
        embed = self._base(
            theme,
            guild,
            title="Тикеты",
            color=theme.color_primary,
            description=(
                "Выберите тему в меню.\n\n"
                + ("\n".join(lines) if lines else "Категории не настроены")
                + f"\n\nЛимит: {max_open} открытых на человека."
            ),
        )
        return embed

    async def ticket_welcome_embed(
        self,
        guild: discord.Guild,
        *,
        ticket_id: int,
        ticket_number: int,
        category,
        opener: discord.Member,
        user_note: str | None = None,
        claimed_by_id: int | None = None,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        body = f"{opener.mention} · {category['emoji']} {category['name']}\nID `{ticket_id}`"
        if user_note and user_note != category["name"]:
            body += f"\n\n**Обращение:**\n{user_note[:900]}"
        else:
            body += "\n\nОпишите проблему, если ещё не указали."
        if claimed_by_id:
            body += f"\n\n✋ В работе: <@{claimed_by_id}>"
        embed = self._base(
            theme,
            guild,
            title=f"Тикет #{ticket_number}",
            color=theme.color_primary,
            description=body,
        )
        return embed

    async def ticket_closed_embed(
        self,
        guild: discord.Guild,
        *,
        ticket: dict,
        ticket_number: str,
        category,
        closed_by: discord.Member,
        reason: str,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        cat_label = category["name"] if category else "—"
        embed = self._base(
            theme,
            guild,
            title="Тикет закрыт",
            color=theme.color_primary,
            description=(
                f"{ticket_number}\n"
                f"<@{ticket['opener_id']}> · закрыл {closed_by.mention}\n"
                f"{cat_label}\n\n"
                f"{reason[:1024] or '—'}"
            ),
        )
        return embed

    async def ticket_statistics_embed(
        self,
        guild: discord.Guild,
        stats: dict[str, int],
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        open_count = int(stats.get("open_count") or 0)
        closed_count = int(stats.get("closed_count") or 0)
        claimed = int(stats.get("claimed_open") or 0)
        total = int(stats.get("total") or 0)
        unclaimed = max(0, open_count - claimed)

        embed = self._base(
            theme,
            guild,
            title="Статистика тикетов",
            color=theme.color_info,
            description=(
                f"Всего **`{total}`** · открыто **`{open_count}`** · закрыто **`{closed_count}`**"
            ),
        )
        embed.add_field(
            name="Открытые",
            value=f"В работе: **`{claimed}`** · ожидают: **`{unclaimed}`**",
            inline=False,
        )
        categories = await self.db.list_ticket_categories(guild.id, enabled_only=False)
        if categories:
            embed.add_field(
                name="Темы",
                value="\n".join(f"{c['emoji']} {c['name']}" for c in categories[:6])[:1024],
                inline=False,
            )
        return embed

    async def ticket_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        theme = await self.theme(guild.id)
        config = await self.db.get_ticket_config(guild.id)
        staff = await self.db.list_ticket_staff_roles(guild.id)
        categories = await self.db.list_ticket_categories(guild.id, enabled_only=False)
        stats = await self.db.ticket_statistics(guild.id)

        cat_ch = guild.get_channel(int(config["discord_category_id"])) if config["discord_category_id"] else None
        log_ch = guild.get_channel(int(config["log_channel_id"])) if config["log_channel_id"] else None
        panel_ch = guild.get_channel(int(config["panel_channel_id"])) if config["panel_channel_id"] else None

        embed = self._base(
            theme,
            guild,
            title="🎫 Настройки тикетов",
            color=theme.color_info,
        )
        embed.add_field(
            name="Каналы",
            value=(
                f"**Категория Discord:** {cat_ch.mention if cat_ch else '—'}\n"
                f"**Логи:** {log_ch.mention if log_ch else '—'}\n"
                f"**Панель:** {panel_ch.mention if panel_ch else '—'}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Staff-роли",
            value=" ".join(f"<@&{r}>" for r in staff) if staff else "—",
            inline=False,
        )
        embed.add_field(
            name="Категории тикетов",
            value=(
                "\n".join(
                    f"`#{c['id']}` {c['emoji']} {c['name']}"
                    + (" · выкл" if not int(c.get("enabled", 1)) else "")
                    for c in categories[:8]
                )
                if categories
                else "—"
            )[:1024],
            inline=False,
        )
        embed.add_field(
            name="Статистика",
            value=(
                f"Открыто: **`{stats.get('open_count', 0)}`** · "
                f"Закрыто: **`{stats.get('closed_count', 0)}`**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Лимиты",
            value=(
                f"Открытых на человека: **`{config['max_open_per_user']}`**\n"
                f"Автор может закрыть: **{'да' if int(config.get('opener_can_close', 1)) else 'нет'}**"
            ),
            inline=True,
        )
        idle_h = int(config.get("idle_close_hours") or 0)
        remind_h = int(config.get("remind_unclaimed_hours") or 0)
        embed.add_field(
            name="Автоматизация",
            value=(
                f"Авто-закрытие: **{'выкл' if idle_h <= 0 else f'{idle_h} ч без активности'}**\n"
                f"Напоминание staff: **{'выкл' if remind_h <= 0 else f'каждые {remind_h} ч'}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Шаблон имени",
            value=(
                f"`{config['name_template']}`\n"
                "🟢 открыт · 🟡 в работе · 🔴 закрыт\n"
                "Пример: `・🟢・поддержка-1054`"
            ),
            inline=False,
        )
        return embed

    async def ticket_audit_embed(
        self,
        guild: discord.Guild,
        issues: list,
        *,
        report=None,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        icons = {"ok": "✅", "warn": "⚠️", "error": "❌"}
        lines = [f"{icons.get(i.level, '•')} {i.text}" for i in issues]
        desc = "\n".join(lines)[:4000]
        embed = self._base(
            theme,
            guild,
            title="🔍 Проверка тикетов",
            color=theme.color_success if all(i.level == "ok" for i in issues) else theme.color_warning,
            description=desc or "—",
        )
        if report is not None:
            actions: list[str] = []
            if report.orphans_closed:
                actions.append(f"Сирот закрыто: **{report.orphans_closed}**")
            if report.idle_closed:
                actions.append(f"Авто-закрыто: **{report.idle_closed}**")
            if report.reminders_sent:
                actions.append(f"Напоминаний: **{report.reminders_sent}**")
            if report.panel_repaired:
                actions.append("Панель восстановлена")
            if actions:
                embed.add_field(name="Обслуживание", value="\n".join(actions), inline=False)
        return embed

    async def ticket_list_embed(
        self,
        guild: discord.Guild,
        tickets: list,
        *,
        status_label: str,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        if not tickets:
            return self._base(
                theme,
                guild,
                title=f"Тикеты · {status_label}",
                color=theme.color_info,
                description="Нет записей.",
            )
        lines: list[str] = []
        for t in tickets[:15]:
            num = t["ticket_number"] or t["id"]
            ch = guild.get_channel(int(t["channel_id"]))
            ch_ref = ch.mention if ch else "`удалён`"
            claim = f" · <@{t['claimed_by_id']}>" if t["claimed_by_id"] else ""
            lines.append(f"**#{num}** {ch_ref} · <@{t['opener_id']}>{claim}")
        return self._base(
            theme,
            guild,
            title=f"Тикеты · {status_label}",
            color=theme.color_info,
            description="\n".join(lines)[:4000],
        )

    async def mod_call_embed(
        self,
        guild: discord.Guild,
        *,
        caller: discord.Member,
        reason: str,
        source_channel: discord.abc.GuildChannel | None = None,
    ) -> discord.Embed:
        theme = await self.theme(guild.id)
        where = source_channel.mention if source_channel else "—"
        embed = self._base(
            theme,
            guild,
            title="🚨 Вызов модератора",
            color=theme.color_danger,
            description=f"{caller.mention} запросил помощь модератора.",
        )
        embed.add_field(name="Причина", value=reason[:1024], inline=False)
        embed.add_field(name="Канал", value=where, inline=True)
        embed.add_field(name="Игрок", value=f"{caller} · `{caller.id}`", inline=True)
        embed.set_footer(text="RU:LC Operations · Mod Call")
        return embed

    async def mod_call_settings_embed(self, guild: discord.Guild) -> discord.Embed:
        theme = await self.theme(guild.id)
        config = await self.db.get_mod_call_config(guild.id)
        roles = await self.db.list_mod_call_roles(guild.id)
        ch = guild.get_channel(int(config["channel_id"])) if config["channel_id"] else None
        cooldown = int(config["cooldown_seconds"] or 0)
        enabled = bool(int(config["enabled"]))
        embed = self._base(
            theme,
            guild,
            title="📢 Вызов модератора",
            color=theme.color_info,
        )
        embed.add_field(
            name="Статус",
            value="✅ включён" if enabled else "⛔ выключен",
            inline=True,
        )
        embed.add_field(
            name="Канал",
            value=ch.mention if ch else "—",
            inline=True,
        )
        embed.add_field(
            name="Кулдаун",
            value=f"**{cooldown}** сек." if cooldown > 0 else "нет",
            inline=True,
        )
        embed.add_field(
            name="Роли для пинга",
            value=" ".join(f"<@&{r}>" for r in roles) if roles else "—",
            inline=False,
        )
        embed.add_field(
            name="Команды",
            value=(
                "`/mod` или `!mod <причина>` — вызов\n"
                "`/mod-настройка канал` · `роль` · `кулдаун`"
            ),
            inline=False,
        )
        return embed
