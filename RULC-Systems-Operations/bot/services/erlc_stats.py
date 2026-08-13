from __future__ import annotations

import io
import logging
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import discord

from bot.db import Database
from bot.services.embeds import EmbedFactory
from bot.services.erlc import ErlcService

logger = logging.getLogger(__name__)

HOUR = 3600
DAY = 86400


class ErlcStatsService:
    def __init__(self, db: Database, erlc: ErlcService, embeds: EmbedFactory) -> None:
        self.db = db
        self.erlc = erlc
        self.embeds = embeds

    async def collect_guild(self, guild_id: int) -> None:
        try:
            count = await self.erlc.get_player_count(guild_id)
            if count is not None:
                await self.db.insert_player_snapshot(guild_id, count)
        except Exception:
            logger.exception("Player snapshot failed for guild %s", guild_id)

        now = int(time.time())
        since = now - DAY

        try:
            join_logs = await self.erlc.fetch_logs(guild_id, "join")
            for entry in join_logs:
                ts = int(entry.timestamp or now)
                if ts < since:
                    continue
                name = entry.name or entry.player or "Unknown"
                uid = str(entry.user_id or name)
                dedup = f"join:{ts}:{uid}:{entry.join}"
                await self.db.insert_log_event(
                    guild_id,
                    "join" if entry.join else "leave",
                    dedup,
                    name,
                    uid,
                    None,
                    None,
                    ts,
                )
        except Exception:
            logger.exception("Join log collect failed for guild %s", guild_id)

        try:
            kill_logs = await self.erlc.fetch_logs(guild_id, "kill")
            for entry in kill_logs:
                ts = int(entry.timestamp or now)
                if ts < since:
                    continue
                killer = entry.killer_name or entry.killer or "Unknown"
                victim = entry.killed_name or entry.killed or "Unknown"
                dedup = f"kill:{ts}:{killer}:{victim}"
                await self.db.insert_log_event(
                    guild_id,
                    "kill",
                    dedup,
                    killer,
                    str(entry.killer_id or killer),
                    victim,
                    str(entry.killed_id or victim),
                    ts,
                )
                await self.db.insert_log_event(
                    guild_id,
                    "death",
                    f"death:{dedup}",
                    victim,
                    str(entry.killed_id or victim),
                    killer,
                    str(entry.killer_id or killer),
                    ts,
                )
        except Exception:
            logger.exception("Kill log collect failed for guild %s", guild_id)

        try:
            cmd_logs = await self.erlc.fetch_logs(guild_id, "command")
            for entry in cmd_logs:
                ts = int(entry.timestamp or now)
                if ts < since:
                    continue
                name = entry.name or entry.player or "Unknown"
                cmd = (entry.command or "").strip()
                if not cmd:
                    continue
                dedup = f"cmd:{ts}:{name}:{cmd[:80]}"
                await self.db.insert_log_event(
                    guild_id,
                    "command",
                    dedup,
                    name,
                    str(entry.user_id or name),
                    cmd,
                    None,
                    ts,
                )
                if cmd.lower().startswith(":spawn") or "vehicle" in cmd.lower():
                    await self.db.insert_log_event(
                        guild_id,
                        "vehicle",
                        f"veh:{dedup}",
                        name,
                        str(entry.user_id or name),
                        cmd,
                        None,
                        ts,
                    )
        except Exception:
            logger.exception("Command log collect failed for guild %s", guild_id)

    def _since_ts(self, hours: int = 24) -> int:
        return int(time.time()) - hours * HOUR

    async def build_players_embed(self, guild: discord.Guild) -> discord.Embed:
        players = await self.erlc.get_players(guild.id)
        try:
            info = await self.erlc.fetch_server_info(guild.id)
        except Exception:
            info = {"players": len(players), "max_players": "?", "name": guild.name}
        return await self.embeds.players_embed(guild, players, info)

    async def build_ranking_embed(
        self,
        guild: discord.Guild,
        title: str,
        emoji: str,
        color_key: str,
        event_type: str,
    ) -> discord.Embed:
        since = self._since_ts(24)
        rows = await self.db.top_players_by_event(guild.id, event_type, since)
        embed = await self.embeds.ranking_embed(
            guild,
            title=title,
            emoji=emoji,
            color_key=color_key,
            rows=rows,
            suffix="раз",
        )
        return embed

    async def activity_ranking(self, guild: discord.Guild) -> discord.Embed:
        since = self._since_ts(24)
        joins = await self.db.get_events_since(guild.id, "join", since)
        leaves = await self.db.get_events_since(guild.id, "leave", since)
        kills = await self.db.get_events_since(guild.id, "kill", since)
        cmds = await self.db.get_events_since(guild.id, "command", since)

        scores: Counter[str] = Counter()
        for row in joins:
            scores[row["player_name"]] += 2
        for row in leaves:
            scores[row["player_name"]] += 1
        for row in kills:
            scores[row["player_name"]] += 1
        for row in cmds:
            scores[row["player_name"]] += 1

        return await self.embeds.activity_embed(guild, scores.most_common(10))

    async def command_ranking_embed(self, guild: discord.Guild) -> discord.Embed:
        since = self._since_ts(24)
        rows = await self.db.get_events_since(guild.id, "command", since)
        counter: Counter[str] = Counter()
        for row in rows:
            cmd = (row["extra_a"] or "").split()[0] or "?"
            counter[cmd] += 1
        return await self.embeds.command_ranking_embed(guild, counter.most_common(10))

    async def _chart_file(
        self,
        guild_id: int,
        title: str,
        labels: list[str],
        values: list[int],
        ylabel: str,
        *,
        line: bool = False,
    ) -> discord.File:
        colors = await self.embeds.chart_colors(guild_id)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 4.5))
        fig.patch.set_facecolor(colors["bg"])
        ax.set_facecolor(colors["bg"])
        if line:
            x = list(range(len(values)))
            ax.plot(x, values, color=colors["success"], marker="o", linewidth=2)
            ax.fill_between(x, values, alpha=0.15, color=colors["success"])
            ax.set_xticks(x)
            ax.set_xticklabels(labels, rotation=32, ha="right")
        else:
            ax.bar(labels, values, color=colors["accent"], edgecolor=colors["grid"])
            plt.xticks(rotation=32, ha="right")
        ax.set_title(title, color=colors["text"], fontsize=13, pad=12)
        ax.set_ylabel(ylabel, color=colors["text"])
        ax.tick_params(colors=colors["text"])
        for spine in ax.spines.values():
            spine.set_color(colors["grid"])
        plt.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=130, facecolor=colors["bg"])
        plt.close(fig)
        buffer.seek(0)
        return discord.File(buffer, filename="chart.png")

    async def chart_players_24h(self, guild_id: int) -> discord.File | None:
        since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        rows = await self.db.get_snapshots_since(guild_id, since)
        if len(rows) < 2:
            return None

        buckets: dict[str, list[int]] = {}
        for row in rows:
            hour_key = str(row["recorded_at"])[:13]
            buckets.setdefault(hour_key, []).append(int(row["player_count"]))

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        labels: list[str] = []
        values: list[int] = []
        for offset in range(23, -1, -1):
            slot = now - timedelta(hours=offset)
            key = slot.strftime("%Y-%m-%d %H")
            counts = buckets.get(key, [])
            labels.append(slot.strftime("%H:00"))
            values.append(round(sum(counts) / len(counts)) if counts else 0)

        if max(values) == 0:
            step = max(1, len(rows) // 24)
            sampled = rows[::step][-24:]
            labels = [str(r["recorded_at"])[11:16] for r in sampled]
            values = [int(r["player_count"]) for r in sampled]

        return await self._chart_file(
            guild_id,
            "Статистика игроков (24ч)",
            labels,
            values,
            "Игроков",
            line=True,
        )

    async def chart_commands_24h(self, guild_id: int) -> discord.File | None:
        since = self._since_ts(24)
        rows = await self.db.get_events_since(guild_id, "command", since)
        if not rows:
            return None
        counter: Counter[str] = Counter()
        for row in rows:
            cmd = (row["extra_a"] or "").split()[0][:32]
            counter[cmd] += 1
        top = counter.most_common(8)
        return await self._chart_file(
            guild_id,
            "Статистика команд (24ч)",
            [c for c, _ in top],
            [n for _, n in top],
            "Использований",
        )

    async def chart_vehicles_24h(self, guild_id: int) -> discord.File | None:
        since = self._since_ts(24)
        rows = await self.db.get_events_since(guild_id, "vehicle", since)
        if not rows:
            return None
        counter: Counter[str] = Counter()
        for row in rows:
            cmd = (row["extra_a"] or "spawn")[:40]
            counter[cmd] += 1
        top = counter.most_common(8)
        return await self._chart_file(
            guild_id,
            "Статистика машин (24ч)",
            [c for c, _ in top],
            [n for _, n in top],
            "Спавнов",
        )

    async def chart_embed(self, guild: discord.Guild, title: str) -> discord.Embed:
        theme = await self.embeds.theme(guild.id)
        return self.embeds._base(
            theme,
            guild,
            title=f"📊 {title}",
            color=theme.color_info,
            description=(
                "График за последние **24 часа**.\n"
                "Данные собираются автоматически каждые **2 мин.**"
            ),
        )
