from __future__ import annotations



from dataclasses import dataclass

from datetime import datetime, timezone

from typing import Any



import discord



from rulc_theme.embeds import finish_minimal

from rulc_theme.tokens import PALETTE



MONTHS_RU = (

    "января",

    "февраля",

    "марта",

    "апреля",

    "мая",

    "июня",

    "июля",

    "августа",

    "сентября",

    "октября",

    "ноября",

    "декабря",

)



TYPE_DISPLAY: dict[str, str] = {

    "warning": "Warning",

    "kick": "Kick",

    "ban": "Ban",

    "bolo": "BOLO",

    "demorgan": "Demorgan",

    "jail": "Demorgan",

    "tempban": "Temp Ban",

    "note": "Note",

}



COLOR_EMBED = PALETTE.neutral

COLOR_OVERVIEW = PALETTE.neutral

COLOR_SUCCESS = PALETTE.success

COLOR_WARNING = PALETTE.warning

COLOR_DANGER = PALETTE.danger

COLOR_INFO = PALETTE.neutral





@dataclass(frozen=True)

class RiskLevel:

    key: str

    label: str

    color: int





def type_label(type_key: str) -> str:

    key = type_key.strip().lower()

    return TYPE_DISPLAY.get(key, type_key.replace("_", " ").title())





def risk_level(points: int) -> RiskLevel:

    if points >= 15:

        return RiskLevel("critical", "Критический", COLOR_DANGER)

    if points >= 10:

        return RiskLevel("high", "Высокий", COLOR_DANGER)

    if points >= 5:

        return RiskLevel("medium", "Средний", COLOR_WARNING)

    if points >= 1:

        return RiskLevel("low", "Низкий", COLOR_EMBED)

    return RiskLevel("clean", "Чистый", COLOR_EMBED)





def risk_color(points: int) -> int:

    return risk_level(points).color





def parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    if value.endswith("Z"):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def to_epoch(value: str | None) -> int | None:
    dt = parse_created_at(value)
    return int(dt.timestamp()) if dt else None


SEARCH_ALERTS = {
    "NoAlerts": "No alerts found for this account!",
    "AccountAge": "The account age of the user is less than 100 days.",
    "NotManyFriends": "This user has less than 30 friends.",
    "HasBOLO": "This user has a BOLO active.",
    "IsBanned": "This user is banned from Roblox.",
}


def punishment_type_counts(punishments: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"warning": 0, "kick": 0, "ban": 0, "bolo": 0, "other": 0}
    for row in punishments:
        key = str(row.get("type_key", "")).lower().strip()
        if key == "warning":
            counts["warning"] += 1
        elif key == "kick":
            counts["kick"] += 1
        elif key in {"ban", "tempban"}:
            counts["ban"] += 1
        elif key == "bolo":
            counts["bolo"] += 1
        else:
            counts["other"] += 1
    return counts


def build_search_alerts(roblox: dict[str, Any], punishments: list[dict[str, Any]]) -> str:
    created_raw = roblox.get("created")
    account_young = False
    if created_raw:
        created_dt = parse_created_at(str(created_raw))
        if created_dt:
            age_days = (datetime.now(timezone.utc) - created_dt).days
            account_young = age_days < 100

    friends = roblox.get("friendCount")
    few_friends = friends is not None and int(friends) < 30
    has_bolo = any(str(p.get("type_key", "")).lower() == "bolo" for p in punishments)
    is_banned = bool(roblox.get("isBanned"))

    triggered: list[str] = []
    if is_banned:
        triggered.append("IsBanned")
    if account_young:
        triggered.append("AccountAge")
    if few_friends:
        triggered.append("NotManyFriends")
    if has_bolo:
        triggered.append("HasBOLO")
    if not triggered:
        triggered.append("NoAlerts")
    return "\n".join(SEARCH_ALERTS[key] for key in triggered)


def search_punishment_value(punishment: dict[str, Any]) -> str:
    staff_id = punishment.get("staff_discord_id")
    if staff_id:
        moderator = f"<@{int(staff_id)}>"
    else:
        moderator = punishment.get("staff_name") or "—"

    lines = [
        f"> **Moderator:** {moderator}",
        f"> **Reason:** {punishment.get('reason') or '—'}",
    ]
    at_epoch = to_epoch(punishment.get("created_at"))
    if at_epoch:
        lines.append(f"> **At:** <t:{at_epoch}>")
    until_epoch = to_epoch(punishment.get("expires_at"))
    if until_epoch:
        lines.append(f"> **Until:** <t:{until_epoch}>")
    case_id = punishment.get("cycle_snowflake") or punishment.get("cycle_case_id") or "—"
    lines.append(f"> **ID:** `{case_id}`")
    return "\n".join(lines)


def _apply_search_author(embed: discord.Embed, author: discord.User | discord.Member) -> None:
    embed.set_author(name=author.display_name, icon_url=author.display_avatar.url)





def format_datetime_ru(dt: datetime | None) -> str:

    if not dt:

        return "—"

    local = dt.astimezone()

    month = MONTHS_RU[local.month - 1]

    return f"{local.day} {month} {local.year}, {local.hour:02d}:{local.minute:02d}"





def format_expires(punishment: dict[str, Any]) -> str:

    if punishment.get("revoked_at"):

        return "отозвано"

    expires = punishment.get("expires_at")

    if expires:

        exp_dt = parse_created_at(str(expires))

        if exp_dt:

            now = datetime.now(timezone.utc)

            if exp_dt <= now:

                return "истекло"

            delta = exp_dt - now

            days = delta.days

            if days >= 60:

                return f"через {max(1, days // 30)} мес."

            if days >= 1:

                return f"через {days} дн."

            return f"через {max(1, delta.seconds // 3600)} ч."

    type_key = str(punishment.get("type_key", "")).lower()

    if type_key in {"ban", "bolo", "demorgan", "jail"}:

        return "бессрочно"

    return "—"





def moderator_line(punishment: dict[str, Any]) -> str:

    staff_id = punishment.get("staff_discord_id")

    staff_name = punishment.get("staff_name")

    if staff_id:

        if staff_name:

            return f"<@{int(staff_id)}> ({staff_name})"

        return f"<@{int(staff_id)}>"

    return staff_name or "—"





def punishment_id_line(punishment: dict[str, Any]) -> str:

    snowflake = punishment.get("cycle_snowflake")

    case_id = punishment.get("cycle_case_id")

    return str(snowflake or case_id or "—")





def punishment_block(punishment: dict[str, Any]) -> str:

    lines = [

        f"Модератор: {moderator_line(punishment)}",

        f"Причина: {punishment.get('reason') or '—'}",

    ]

    description = punishment.get("description")

    if description:

        lines.append(f"Описание: {description}")

    lines.append(

        f"{punishment.get('points', 0)} б. · #{punishment_id_line(punishment)} · "

        f"{format_datetime_ru(parse_created_at(punishment.get('created_at')))} · "

        f"{format_expires(punishment)}"

    )

    return "\n".join(lines)





def _finish(embed: discord.Embed, guild_name: str | None = None, extra: str = "") -> discord.Embed:

    return finish_minimal(embed, page=extra or None)





def _rank_label(rank: int) -> str:

    return f"{rank}."





class RobloxEmbedFactory:

    @staticmethod

    def _finish(

        embed: discord.Embed,

        guild_name: str | None = None,

        extra: str = "",

    ) -> discord.Embed:

        return _finish(embed, guild_name, extra)



    @staticmethod
    def overview_embed(
        roblox: dict[str, Any],
        *,
        punishments: list[dict[str, Any]],
        total_points: int,
        author: discord.User | discord.Member,
        guild_name: str | None = None,
        total_pages: int = 1,
    ) -> discord.Embed:
        """Страница 1 — как CycleRM /search."""
        name = roblox.get("name") or "—"
        rid = int(roblox["id"])
        display = roblox.get("displayName", name)
        friends = roblox.get("friendCount")
        created_epoch = to_epoch(str(roblox.get("created"))) if roblox.get("created") else None
        counts = punishment_type_counts(punishments)
        total = len(punishments)

        embed = discord.Embed(title=name, color=COLOR_EMBED)
        embed.add_field(
            name="Player Information",
            value=(
                f"> **Username:** {name}\n"
                f"> **Display Name:** {display}\n"
                f"> **User ID:** `{rid}`\n"
                f"> **Friend Count:** {friends if friends is not None else '—'}\n"
                f"{f'> **Created At:** <t:{created_epoch}>' if created_epoch else '> **Created At:** —'}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Punishments",
            value=(
                f"> **Total Punishments:** {total}\n"
                f"> **Warnings:** {counts['warning']}\n"
                f"> **Kicks:** {counts['kick']}\n"
                f"> **Bans:** {counts['ban']}\n"
                f"> **BOLOs:** {counts['bolo']}\n"
                f"> **Other:** {counts['other']}\n"
                f"> **Points:** {total_points}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Player Alerts",
            value=build_search_alerts(roblox, punishments),
            inline=False,
        )
        if roblox.get("avatar_url"):
            embed.set_thumbnail(url=roblox["avatar_url"])
        _apply_search_author(embed, author)
        page_hint = f"{1}/{total_pages}" if total_pages > 1 else ""
        return RobloxEmbedFactory._finish(embed, guild_name, page_hint)

    @staticmethod
    def punishments_embed(
        roblox: dict[str, Any],
        punishments: list[dict[str, Any]],
        *,
        page_index: int,
        total_pages: int,
        author: discord.User | discord.Member,
        guild_name: str | None = None,
    ) -> discord.Embed:
        """Страницы наказаний — как CycleRM /search."""
        name = roblox.get("name") or "—"
        embed = discord.Embed(title=name, color=COLOR_EMBED)
        for punishment in punishments:
            field_name = type_label(str(punishment["type_key"]))
            embed.add_field(
                name=field_name,
                value=search_punishment_value(punishment)[:1024],
                inline=False,
            )
        if roblox.get("avatar_url"):
            embed.set_thumbnail(url=roblox["avatar_url"])
        _apply_search_author(embed, author)
        return RobloxEmbedFactory._finish(embed, guild_name, f"{page_index + 1}/{total_pages}")



    @staticmethod

    def points_card(

        roblox: dict[str, Any],

        *,

        total_points: int,

        breakdown: list[dict[str, Any]],

        guild_name: str | None = None,

    ) -> discord.Embed:

        name = roblox.get("name") or "—"

        risk = risk_level(total_points)

        lines = [f"Итого `{total_points}` · {risk.label}"]

        if breakdown:

            for row in breakdown:

                lines.append(

                    f"{type_label(str(row['type_key']))}: {row['qty']} × {row['points']} б."

                )

        else:

            lines.append("Нет активных наказаний.")



        embed = discord.Embed(title=name, description="\n".join(lines), color=risk.color)

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def leaderboard_embed(

        rows: list[dict[str, Any]],

        *,

        guild_name: str | None = None,

        title: str = "Топ по баллам",

    ) -> discord.Embed:

        if not rows:

            embed = discord.Embed(

                title=title,

                description="Нет игроков с активными баллами.",

                color=COLOR_EMBED,

            )

            return RobloxEmbedFactory._finish(embed, guild_name)



        lines = []

        for i, row in enumerate(rows, start=1):

            lines.append(

                f"{_rank_label(i)} [{row['roblox_name']}]"

                f"(https://www.roblox.com/users/{row['roblox_id']}/profile) — "

                f"{row['total_points']} б."

            )

        embed = discord.Embed(title=title, description="\n".join(lines)[:4096], color=COLOR_EMBED)

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def compare_embed(

        player_a: dict[str, Any],

        points_a: int,

        player_b: dict[str, Any],

        points_b: int,

        *,

        guild_name: str | None = None,

    ) -> discord.Embed:

        name_a = player_a.get("name", "?")

        name_b = player_b.get("name", "?")

        diff = points_a - points_b

        if diff > 0:

            verdict = f"{name_a} +{diff} к {name_b}"

        elif diff < 0:

            verdict = f"{name_b} +{-diff} к {name_a}"

        else:

            verdict = "Одинаково"



        embed = discord.Embed(

            title="Сравнение",

            description=(

                f"{verdict}\n\n"

                f"{name_a} — {points_a} б. ({risk_level(points_a).label})\n"

                f"{name_b} — {points_b} б. ({risk_level(points_b).label})"

            ),

            color=COLOR_EMBED,

        )

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def radar_embed(

        rows: list[dict[str, Any]],

        *,

        threshold: int,

        guild_name: str | None = None,

    ) -> discord.Embed:

        if not rows:

            embed = discord.Embed(

                title="Радар",

                description=f"Никто не выше {threshold} б.",

                color=COLOR_EMBED,

            )

            return RobloxEmbedFactory._finish(embed, guild_name)



        lines = [

            f"[{row['roblox_name']}](https://www.roblox.com/users/{row['roblox_id']}/profile)"

            f" — {row['total_points']} б. ({row['active_count']} наказ.)"

            for row in rows

        ]

        embed = discord.Embed(

            title=f"Радар · {threshold}+ б.",

            description="\n".join(lines)[:4096],

            color=COLOR_WARNING,

        )

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def risk_embed(

        roblox: dict[str, Any],

        *,

        total_points: int,

        breakdown: list[dict[str, Any]],

        guild_name: str | None = None,

    ) -> discord.Embed:

        risk = risk_level(total_points)

        name = roblox.get("name") or "—"

        lines = [f"{risk.label} · {total_points} б."]

        if breakdown:

            types = ", ".join(type_label(str(r["type_key"])) for r in breakdown[:5])

            lines.append(types)



        embed = discord.Embed(title=name, description="\n".join(lines), color=risk.color)

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def journal_embed(

        rows: list[dict[str, Any]],

        *,

        guild_name: str | None = None,

    ) -> discord.Embed:

        if not rows:

            embed = discord.Embed(title="Журнал", description="Записей нет.", color=COLOR_EMBED)

            return RobloxEmbedFactory._finish(embed, guild_name)



        lines = []

        for row in rows:

            ts = format_datetime_ru(parse_created_at(row.get("created_at")))

            revoked = " · отозвано" if row.get("revoked_at") else ""

            lines.append(

                f"{type_label(str(row['type_key']))} · "

                f"[{row['roblox_name']}](https://www.roblox.com/users/{row['roblox_id']}/profile)\n"

                f"{row.get('points', 0)} б. · {ts}{revoked} · {row.get('reason') or '—'}"

            )

        embed = discord.Embed(title="Журнал", description="\n\n".join(lines)[:4096], color=COLOR_EMBED)

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def guild_stats_embed(

        stats: dict[str, Any],

        *,

        guild: discord.Guild,

    ) -> discord.Embed:

        top_types = stats.get("top_types") or []

        type_lines = [f"{type_label(str(r['type_key']))}: {r['qty']}" for r in top_types]

        description = (

            f"Записей {stats.get('total_records', 0)} · "

            f"активных {stats.get('active_count', 0)} · "

            f"отозванных {stats.get('revoked_count', 0)}\n"

            f"Баллов {stats.get('active_points', 0)} · "

            f"игроков {stats.get('unique_players', 0)} · "

            f"staff {stats.get('unique_staff', 0)}\n"

            f"Высокий риск (10+): {stats.get('high_risk_players', 0)}"

        )

        if type_lines:

            description += "\n\n" + "\n".join(type_lines)



        embed = discord.Embed(title="Статистика", description=description, color=COLOR_EMBED)

        return RobloxEmbedFactory._finish(embed, guild.name)



    @staticmethod

    def moderator_embed(

        member: discord.Member,

        stats: dict[str, Any],

        *,

        guild_name: str | None = None,

    ) -> discord.Embed:

        by_type = stats.get("by_type") or []

        lines = [

            f"Дел {stats.get('total_cases', 0)} · "

            f"активных {stats.get('active_cases', 0)} · "

            f"баллов {stats.get('points_given', 0)}"

        ]

        if by_type:

            lines.extend(f"{type_label(str(r['type_key']))}: {r['qty']}" for r in by_type)



        embed = discord.Embed(

            title=str(member.display_name),

            description="\n".join(lines),

            color=COLOR_EMBED,

        )

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def moderator_top_embed(

        rows: list[dict[str, Any]],

        *,

        guild_name: str | None = None,

    ) -> discord.Embed:

        if not rows:

            embed = discord.Embed(title="Staff", description="Нет данных.", color=COLOR_EMBED)

            return RobloxEmbedFactory._finish(embed, guild_name)



        lines = []

        for i, row in enumerate(rows, start=1):

            mention = f"<@{row['staff_discord_id']}>"

            lines.append(

                f"{_rank_label(i)} {mention} — {row['cases']} дел, {row['points_given']} б."

            )

        embed = discord.Embed(title="Staff", description="\n".join(lines)[:4096], color=COLOR_EMBED)

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def rules_embed(

        rules: list[dict[str, Any]],

        *,

        guild_name: str | None = None,

    ) -> discord.Embed:

        lines = [f"{type_label(str(r['type_key']))}: {r['points']} б." for r in rules]

        embed = discord.Embed(

            title="Правила баллов",

            description="\n".join(lines) or "—",

            color=COLOR_EMBED,

        )

        return RobloxEmbedFactory._finish(embed, guild_name)



    @staticmethod

    def help_embed() -> discord.Embed:

        embed = discord.Embed(

            title="Roblox",

            description=(

                "Наказания синхронизируются из CycleRM.\n\n"

                "`/поиск` `/баллы` `/риск` `/сравнить`\n"

                "`/топ` `/радар` `/журнал` `/статистика`\n"

                "`/модератор` `/staff-топ`\n"

                "`/правила` `/установить-баллы`"

            ),

            color=COLOR_EMBED,

        )

        return RobloxEmbedFactory._finish(embed)





SearchEmbedFactory = RobloxEmbedFactory


