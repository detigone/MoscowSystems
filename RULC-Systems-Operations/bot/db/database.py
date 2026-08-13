from __future__ import annotations

import aiosqlite

from bot.db.schema import SCHEMA


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if not self._conn:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def create_sync_group(self, name: str) -> int:
        cursor = await self.conn.execute(
            "INSERT INTO sync_groups (name) VALUES (?)",
            (name,),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def delete_sync_group(self, name: str) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM sync_groups WHERE name = ?",
            (name,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_sync_group(self, name: str) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM sync_groups WHERE name = ?",
            (name,),
        )
        return await cursor.fetchone()

    async def list_sync_groups(self) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute("SELECT * FROM sync_groups ORDER BY name")
        return await cursor.fetchall()

    async def add_guild_to_group(self, group_name: str, guild_id: int) -> bool:
        group = await self.get_sync_group(group_name)
        if not group:
            return False
        await self.conn.execute(
            "INSERT OR IGNORE INTO sync_group_guilds (group_id, guild_id) VALUES (?, ?)",
            (group["id"], guild_id),
        )
        await self.conn.commit()
        return True

    async def remove_guild_from_group(self, group_name: str, guild_id: int) -> bool:
        group = await self.get_sync_group(group_name)
        if not group:
            return False
        cursor = await self.conn.execute(
            "DELETE FROM sync_group_guilds WHERE group_id = ? AND guild_id = ?",
            (group["id"], guild_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_group_guilds(self, group_id: int) -> list[int]:
        cursor = await self.conn.execute(
            "SELECT guild_id FROM sync_group_guilds WHERE group_id = ?",
            (group_id,),
        )
        rows = await cursor.fetchall()
        return [row["guild_id"] for row in rows]

    async def get_groups_for_guild(self, guild_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT g.*
            FROM sync_groups g
            JOIN sync_group_guilds gg ON gg.group_id = g.id
            WHERE gg.guild_id = ?
            """,
            (guild_id,),
        )
        return await cursor.fetchall()

    async def add_synced_role(self, group_name: str, role_name: str) -> bool:
        group = await self.get_sync_group(group_name)
        if not group:
            return False
        await self.conn.execute(
            "INSERT OR IGNORE INTO synced_roles (group_id, role_name) VALUES (?, ?)",
            (group["id"], role_name.lower()),
        )
        await self.conn.commit()
        return True

    async def remove_synced_role(self, group_name: str, role_name: str) -> bool:
        group = await self.get_sync_group(group_name)
        if not group:
            return False
        cursor = await self.conn.execute(
            "DELETE FROM synced_roles WHERE group_id = ? AND role_name = ?",
            (group["id"], role_name.lower()),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_synced_roles(self, group_id: int) -> list[str]:
        cursor = await self.conn.execute(
            "SELECT role_name FROM synced_roles WHERE group_id = ? ORDER BY role_name",
            (group_id,),
        )
        rows = await cursor.fetchall()
        return [row["role_name"] for row in rows]

    async def add_role_mapping(
        self,
        group_name: str,
        source_guild_id: int,
        source_role_id: int,
        target_guild_id: int,
        target_role_id: int,
    ) -> bool:
        group = await self.get_sync_group(group_name)
        if not group:
            return False
        await self.conn.execute(
            """
            INSERT OR REPLACE INTO role_mappings
            (group_id, source_guild_id, source_role_id, target_guild_id, target_role_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (group["id"], source_guild_id, source_role_id, target_guild_id, target_role_id),
        )
        await self.conn.commit()
        return True

    async def get_role_mappings(self, group_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            "SELECT * FROM role_mappings WHERE group_id = ?",
            (group_id,),
        )
        return await cursor.fetchall()

    async def set_erlc_server(self, guild_id: int, server_key: str, server_name: str | None) -> None:
        await self.conn.execute(
            """
            INSERT INTO erlc_servers (guild_id, server_key, server_name, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(guild_id) DO UPDATE SET
                server_key = excluded.server_key,
                server_name = excluded.server_name,
                updated_at = datetime('now')
            """,
            (guild_id, server_key, server_name),
        )
        await self.conn.commit()

    async def get_erlc_server(self, guild_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM erlc_servers WHERE guild_id = ?",
            (guild_id,),
        )
        return await cursor.fetchone()

    async def remove_erlc_server(self, guild_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM erlc_servers WHERE guild_id = ?",
            (guild_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def list_erlc_guilds(self) -> list[int]:
        cursor = await self.conn.execute("SELECT guild_id FROM erlc_servers")
        rows = await cursor.fetchall()
        return [row["guild_id"] for row in rows]

    async def upsert_guild_registry(
        self,
        guild_id: int,
        guild_name: str,
        icon_url: str | None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO guild_registry (guild_id, guild_name, icon_url, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(guild_id) DO UPDATE SET
                guild_name = excluded.guild_name,
                icon_url = excluded.icon_url,
                updated_at = datetime('now')
            """,
            (guild_id, guild_name, icon_url),
        )
        await self.conn.commit()

    async def list_registered_guilds(self) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            "SELECT * FROM guild_registry ORDER BY guild_name COLLATE NOCASE"
        )
        return await cursor.fetchall()

    async def get_guild_autoroles(self, guild_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM guild_autoroles WHERE guild_id = ?",
            (guild_id,),
        )
        return await cursor.fetchone()

    async def set_guild_autoroles(
        self,
        guild_id: int,
        member_role_id: int | None = None,
        bot_role_id: int | None = None,
        member_enabled: bool = True,
        bot_enabled: bool = True,
    ) -> None:
        existing = await self.get_guild_autoroles(guild_id)
        member_id = member_role_id if member_role_id is not None else (
            existing["member_role_id"] if existing else None
        )
        bot_id = bot_role_id if bot_role_id is not None else (
            existing["bot_role_id"] if existing else None
        )
        await self.conn.execute(
            """
            INSERT INTO guild_autoroles
            (guild_id, member_role_id, bot_role_id, member_enabled, bot_enabled)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                member_role_id = excluded.member_role_id,
                bot_role_id = excluded.bot_role_id,
                member_enabled = excluded.member_enabled,
                bot_enabled = excluded.bot_enabled
            """,
            (guild_id, member_id, bot_id, int(member_enabled), int(bot_enabled)),
        )
        await self.conn.commit()

    async def create_conditional_rule(
        self,
        guild_id: int,
        name: str,
        target_role_id: int,
        trigger_role_ids: list[int],
        remove_on_loss: bool = True,
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO conditional_role_rules
            (guild_id, name, target_role_id, remove_on_loss)
            VALUES (?, ?, ?, ?)
            """,
            (guild_id, name, target_role_id, int(remove_on_loss)),
        )
        rule_id = cursor.lastrowid
        for role_id in trigger_role_ids:
            await self.conn.execute(
                "INSERT INTO conditional_role_triggers (rule_id, trigger_role_id) VALUES (?, ?)",
                (rule_id, role_id),
            )
        await self.conn.commit()
        return rule_id

    async def update_conditional_rule(
        self,
        rule_id: int,
        name: str,
        target_role_id: int,
        trigger_role_ids: list[int],
        remove_on_loss: bool,
        enabled: bool,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE conditional_role_rules
            SET name = ?, target_role_id = ?, remove_on_loss = ?, enabled = ?
            WHERE id = ?
            """,
            (name, target_role_id, int(remove_on_loss), int(enabled), rule_id),
        )
        await self.conn.execute(
            "DELETE FROM conditional_role_triggers WHERE rule_id = ?",
            (rule_id,),
        )
        for role_id in trigger_role_ids:
            await self.conn.execute(
                "INSERT INTO conditional_role_triggers (rule_id, trigger_role_id) VALUES (?, ?)",
                (rule_id, role_id),
            )
        await self.conn.commit()

    async def delete_conditional_rule(self, rule_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM conditional_role_rules WHERE id = ?",
            (rule_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_conditional_rules(self, guild_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM conditional_role_rules
            WHERE guild_id = ?
            ORDER BY name
            """,
            (guild_id,),
        )
        return await cursor.fetchall()

    async def get_conditional_rule(self, rule_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM conditional_role_rules WHERE id = ?",
            (rule_id,),
        )
        return await cursor.fetchone()

    async def get_conditional_triggers(self, rule_id: int) -> list[int]:
        cursor = await self.conn.execute(
            "SELECT trigger_role_id FROM conditional_role_triggers WHERE rule_id = ?",
            (rule_id,),
        )
        rows = await cursor.fetchall()
        return [row["trigger_role_id"] for row in rows]

    async def create_broadcast_source(
        self,
        source_guild_id: int,
        source_channel_id: int,
        name: str,
        require_role_id: int | None = None,
        embed_color: str = "#5865F2",
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO broadcast_sources
            (source_guild_id, source_channel_id, name, require_role_id, embed_color)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_guild_id, source_channel_id, name, require_role_id, embed_color),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def update_broadcast_source(
        self,
        source_id: int,
        name: str,
        enabled: bool,
        require_role_id: int | None,
        embed_color: str,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE broadcast_sources
            SET name = ?, enabled = ?, require_role_id = ?, embed_color = ?
            WHERE id = ?
            """,
            (name, int(enabled), require_role_id, embed_color, source_id),
        )
        await self.conn.commit()

    async def delete_broadcast_source(self, source_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM broadcast_sources WHERE id = ?",
            (source_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_broadcast_source(self, source_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM broadcast_sources WHERE id = ?",
            (source_id,),
        )
        return await cursor.fetchone()

    async def get_broadcast_source_by_channel(self, channel_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM broadcast_sources WHERE source_channel_id = ? AND enabled = 1",
            (channel_id,),
        )
        return await cursor.fetchone()

    async def list_broadcast_sources(self, guild_id: int | None = None) -> list[aiosqlite.Row]:
        if guild_id is None:
            cursor = await self.conn.execute(
                "SELECT * FROM broadcast_sources ORDER BY source_guild_id, name"
            )
        else:
            cursor = await self.conn.execute(
                """
                SELECT * FROM broadcast_sources
                WHERE source_guild_id = ?
                ORDER BY name
                """,
                (guild_id,),
            )
        return await cursor.fetchall()

    async def add_broadcast_target(
        self,
        source_id: int,
        name: str,
        webhook_url: str,
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO broadcast_targets (source_id, name, webhook_url)
            VALUES (?, ?, ?)
            """,
            (source_id, name, webhook_url),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def update_broadcast_target(
        self,
        target_id: int,
        name: str,
        webhook_url: str,
        enabled: bool,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE broadcast_targets
            SET name = ?, webhook_url = ?, enabled = ?
            WHERE id = ?
            """,
            (name, webhook_url, int(enabled), target_id),
        )
        await self.conn.commit()

    async def delete_broadcast_target(self, target_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM broadcast_targets WHERE id = ?",
            (target_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_broadcast_targets(self, source_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM broadcast_targets
            WHERE source_id = ?
            ORDER BY name
            """,
            (source_id,),
        )
        return await cursor.fetchall()

    async def set_voice_counter(
        self,
        guild_id: int,
        channel_id: int,
        name_template: str | None = None,
        enabled: bool = True,
    ) -> None:
        template = name_template or "╭・📡 ・Игроков на сервере: {count}"
        await self.conn.execute(
            """
            INSERT INTO voice_player_counters (guild_id, channel_id, name_template, enabled)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                name_template = excluded.name_template,
                enabled = excluded.enabled
            """,
            (guild_id, channel_id, template, int(enabled)),
        )
        await self.conn.commit()

    async def get_voice_counter(self, guild_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM voice_player_counters WHERE guild_id = ? AND enabled = 1",
            (guild_id,),
        )
        return await cursor.fetchone()

    async def list_voice_counters(self) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            "SELECT * FROM voice_player_counters WHERE enabled = 1"
        )
        return await cursor.fetchall()

    async def disable_voice_counter(self, guild_id: int) -> bool:
        cursor = await self.conn.execute(
            "UPDATE voice_player_counters SET enabled = 0 WHERE guild_id = ?",
            (guild_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def insert_log_event(
        self,
        guild_id: int,
        event_type: str,
        dedup_key: str,
        player_name: str | None,
        player_id: str | None,
        extra_a: str | None,
        extra_b: str | None,
        event_ts: int,
    ) -> bool:
        try:
            await self.conn.execute(
                """
                INSERT INTO erlc_log_events
                (guild_id, event_type, dedup_key, player_name, player_id, extra_a, extra_b, event_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (guild_id, event_type, dedup_key, player_name, player_id, extra_a, extra_b, event_ts),
            )
            await self.conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def insert_player_snapshot(self, guild_id: int, player_count: int) -> None:
        await self.conn.execute(
            """
            INSERT INTO erlc_player_snapshots (guild_id, player_count)
            VALUES (?, ?)
            """,
            (guild_id, player_count),
        )
        await self.conn.commit()

    async def get_events_since(self, guild_id: int, event_type: str, since_ts: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM erlc_log_events
            WHERE guild_id = ? AND event_type = ? AND event_ts >= ?
            ORDER BY event_ts DESC
            """,
            (guild_id, event_type, since_ts),
        )
        return await cursor.fetchall()

    async def get_snapshots_since(self, guild_id: int, since_iso: str) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM erlc_player_snapshots
            WHERE guild_id = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
            """,
            (guild_id, since_iso),
        )
        return await cursor.fetchall()

    async def top_players_by_event(
        self,
        guild_id: int,
        event_type: str,
        since_ts: int,
        field: str = "player_name",
        limit: int = 10,
    ) -> list[tuple[str, int]]:
        col = "player_name" if field == "player_name" else "extra_a"
        cursor = await self.conn.execute(
            f"""
            SELECT {col} AS label, COUNT(*) AS cnt
            FROM erlc_log_events
            WHERE guild_id = ? AND event_type = ? AND event_ts >= ? AND {col} IS NOT NULL
            GROUP BY {col}
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (guild_id, event_type, since_ts, limit),
        )
        rows = await cursor.fetchall()
        return [(row["label"], row["cnt"]) for row in rows if row["label"]]

    async def get_embed_settings(self, guild_id: int) -> aiosqlite.Row:
        cursor = await self.conn.execute(
            "SELECT * FROM guild_embed_settings WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        if row:
            return row
        await self.conn.execute(
            "INSERT INTO guild_embed_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        await self.conn.commit()
        cursor = await self.conn.execute(
            "SELECT * FROM guild_embed_settings WHERE guild_id = ?",
            (guild_id,),
        )
        return await cursor.fetchone()

    async def update_embed_settings(self, guild_id: int, **fields: str | int | bool | None) -> None:
        await self.get_embed_settings(guild_id)
        allowed = {
            "brand_name",
            "footer_text",
            "thumbnail_url",
            "color_primary",
            "color_success",
            "color_warning",
            "color_danger",
            "color_info",
            "show_timestamp",
            "use_guild_icon",
            "players_per_field",
        }
        parts: list[str] = []
        values: list[object] = []
        for key, value in fields.items():
            if key not in allowed or value is None:
                continue
            if key in {"show_timestamp", "use_guild_icon"}:
                value = int(bool(value))
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return
        values.append(guild_id)
        await self.conn.execute(
            f"UPDATE guild_embed_settings SET {', '.join(parts)} WHERE guild_id = ?",
            values,
        )
        await self.conn.commit()

    async def reset_embed_settings(self, guild_id: int) -> None:
        await self.conn.execute(
            "DELETE FROM guild_embed_settings WHERE guild_id = ?",
            (guild_id,),
        )
        await self.conn.commit()
        await self.get_embed_settings(guild_id)
