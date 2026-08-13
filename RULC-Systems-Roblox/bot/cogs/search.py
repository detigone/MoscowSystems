from __future__ import annotations

import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

TYPE_LABELS = {
    "warning": "Предупреждения",
    "kick": "Кики",
    "ban": "Баны",
    "bolo": "BOLO",
}

CONNECTOR = "├"
LAST_CONNECTOR = "└"


async def fetch_roblox_user(username: str) -> dict | None:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://users.roblox.com/v1/usernames/users",
            json={"usernames": [username], "excludeBannedUsers": False},
        ) as resp:
            if resp.status >= 400:
                return None
            data = await resp.json()
            users = data.get("data") or []
            if not users:
                return None
            user = users[0]
        async with session.get(f"https://users.roblox.com/v1/users/{user['id']}") as resp:
            if resp.status >= 400:
                return user
            profile = await resp.json()
            user.update(profile)
        async with session.get(
            f"https://thumbnails.roblox.com/v1/users/avatar-headshot"
            f"?userIds={user['id']}&size=150x150&format=Png&isCircular=false"
        ) as resp:
            if resp.status == 200:
                thumb_data = await resp.json()
                items = thumb_data.get("data") or []
                if items:
                    user["avatar_url"] = items[0].get("imageUrl")
    return user


class SearchCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def nickname_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        db = interaction.client.db  # type: ignore[attr-defined]
        recent = await db.recent_moderated_names(interaction.guild.id, 15)
        cached = await db.search_names(interaction.guild.id, current, 15) if current else []

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

    @app_commands.command(
        name="поиск",
        description="Roblox профиль и наказания игрока",
    )
    @app_commands.describe(
        никнейм="Roblox никнейм игрока, у которого вы хотите просмотреть наказания.",
    )
    @app_commands.autocomplete(никнейм=nickname_autocomplete)
    async def poisk(self, interaction: discord.Interaction, никнейм: str) -> None:
        if not interaction.guild:
            await interaction.response.send_message("Только на сервере.", ephemeral=True)
            return

        await interaction.response.defer()

        roblox = await fetch_roblox_user(никнейм.strip())
        if not roblox:
            return await interaction.followup.send(
                f"Игрок **`{никнейм}`** не найден в Roblox.",
                ephemeral=True,
            )

        db = self.bot.db
        gid = interaction.guild.id
        rid = int(roblox["id"])
        total_points = await db.sum_points(gid, rid)
        breakdown = await db.punishment_breakdown(gid, rid)

        by_type = {row["type_key"]: row for row in breakdown}
        ordered_keys = ["warning", "kick", "ban", "bolo"]
        extra_keys = [k for k in by_type if k not in ordered_keys]

        lines: list[str] = []
        if total_points <= 0:
            lines.append("**Всего баллов:** Баллов нет.")
        else:
            lines.append(f"**Всего баллов:** {total_points}")

        all_keys = ordered_keys + extra_keys
        for idx, key in enumerate(all_keys):
            row = by_type.get(key)
            label = TYPE_LABELS.get(key, key.capitalize())
            qty = int(row["qty"]) if row else 0
            pts = int(row["points"]) if row else 0
            prefix = LAST_CONNECTOR if idx == len(all_keys) - 1 else CONNECTOR
            lines.append(f"{prefix} **{label}:**")
            lines.append(f"   Количество: {qty}")
            lines.append(f"   Баллы: {pts}")

        alerts: list[str] = []
        friends = roblox.get("friendCount")
        if friends is not None and friends < 30:
            alerts.append("У пользователя менее 30 друзей.")

        embed = discord.Embed(
            title=roblox.get("name") or никнейм,
            color=0x5865F2,
        )
        if roblox.get("avatar_url"):
            embed.set_thumbnail(url=roblox["avatar_url"])

        embed.add_field(
            name="Информация о пользователе",
            value=(
                f"> **Никнейм:** [{roblox.get('name', никнейм)}]"
                f"(https://www.roblox.com/users/{rid}/profile)\n"
                f"> **Отображаемое имя:** {roblox.get('displayName', roblox.get('name', '—'))}\n"
                f"> **Айди пользователя:** `{rid}`\n"
                f"> **Количество друзей:** {friends if friends is not None else '—'}"
            ),
            inline=False,
        )
        embed.add_field(name="Наказания", value="\n".join(lines), inline=False)
        if alerts:
            embed.add_field(
                name="Алерты игрока",
                value="\n".join(f"⚠ {a}" for a in alerts),
                inline=False,
            )
        embed.set_footer(text="RU:LC Systems Roblox")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SearchCog(bot))
