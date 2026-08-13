from __future__ import annotations

import aiosqlite

from bot.db.schema import SCHEMA
from bot.services.secrets_store import SecretsStore


class Database:
    def __init__(self, path: str, *, secrets: SecretsStore | None = None) -> None:
        self.path = path
        self.secrets = secrets or SecretsStore(None)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._migrate_ticket_schema()
        await self._conn.commit()

    async def _migrate_ticket_schema(self) -> None:
        cursor = await self.conn.execute("PRAGMA table_info(tickets)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "ticket_number" not in columns:
            await self.conn.execute("ALTER TABLE tickets ADD COLUMN ticket_number INTEGER")
        if "control_message_id" not in columns:
            await self.conn.execute("ALTER TABLE tickets ADD COLUMN control_message_id INTEGER")

        cursor = await self.conn.execute("PRAGMA table_info(ticket_config)")
        config_cols = {row[1] for row in await cursor.fetchall()}
        if "opener_can_close" not in config_cols:
            await self.conn.execute(
                "ALTER TABLE ticket_config ADD COLUMN opener_can_close INTEGER NOT NULL DEFAULT 1"
            )
        if "idle_close_hours" not in config_cols:
            await self.conn.execute(
                "ALTER TABLE ticket_config ADD COLUMN idle_close_hours INTEGER NOT NULL DEFAULT 0"
            )
        if "remind_unclaimed_hours" not in config_cols:
            await self.conn.execute(
                "ALTER TABLE ticket_config ADD COLUMN remind_unclaimed_hours INTEGER NOT NULL DEFAULT 0"
            )

        if "last_activity_at" not in columns:
            await self.conn.execute("ALTER TABLE tickets ADD COLUMN last_activity_at TEXT")
        if "last_staff_ping_at" not in columns:
            await self.conn.execute("ALTER TABLE tickets ADD COLUMN last_staff_ping_at TEXT")
        await self.conn.execute(
            """
            UPDATE tickets SET last_activity_at = created_at
            WHERE last_activity_at IS NULL
            """
        )

        await self.conn.execute(
            """
            UPDATE ticket_config
            SET name_template = '・{step}・{category}-{number}'
            WHERE name_template IN ('ticket-{number}', '{category}-{number}')
            """
        )

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
        sealed_key = self.secrets.seal(server_key)
        await self.conn.execute(
            """
            INSERT INTO erlc_servers (guild_id, server_key, server_name, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(guild_id) DO UPDATE SET
                server_key = excluded.server_key,
                server_name = excluded.server_name,
                updated_at = datetime('now')
            """,
            (guild_id, sealed_key, server_name),
        )
        await self.conn.commit()

    async def get_erlc_server(self, guild_id: int) -> dict | None:
        cursor = await self.conn.execute(
            "SELECT * FROM erlc_servers WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["server_key"] = self.secrets.open(str(data["server_key"]))
        return data

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
        embed_color: str = "#4FC3F7",
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
        sealed_url = self.secrets.seal(webhook_url)
        cursor = await self.conn.execute(
            """
            INSERT INTO broadcast_targets (source_id, name, webhook_url)
            VALUES (?, ?, ?)
            """,
            (source_id, name, sealed_url),
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
        sealed_url = self.secrets.seal(webhook_url)
        await self.conn.execute(
            """
            UPDATE broadcast_targets
            SET name = ?, webhook_url = ?, enabled = ?
            WHERE id = ?
            """,
            (name, sealed_url, int(enabled), target_id),
        )
        await self.conn.commit()

    async def delete_broadcast_target(self, target_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM broadcast_targets WHERE id = ?",
            (target_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def get_broadcast_targets(self, source_id: int) -> list[dict]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM broadcast_targets
            WHERE source_id = ?
            ORDER BY name
            """,
            (source_id,),
        )
        rows = await cursor.fetchall()
        result: list[dict] = []
        for row in rows:
            data = dict(row)
            data["webhook_url"] = self.secrets.open(str(data["webhook_url"]))
            result.append(data)
        return result

    async def get_max_event_ts(self, guild_id: int) -> int | None:
        cursor = await self.conn.execute(
            "SELECT MAX(event_ts) FROM erlc_log_events WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        if not row or row[0] is None:
            return None
        return int(row[0])

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

    # ── Tickets ───────────────────────────────────────────────────────────

    DEFAULT_TICKET_CATEGORIES = (
        ("Поддержка", "🛟", "Общие вопросы и помощь"),
        ("Жалоба", "🚨", "Жалоба на игрока или staff"),
        ("Апелляция", "⚖️", "Обжалование наказания"),
        ("Другое", "📩", "Всё остальное"),
    )

    async def ensure_ticket_config(self, guild_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO ticket_config (guild_id) VALUES (?)",
            (guild_id,),
        )
        for name, emoji, desc in self.DEFAULT_TICKET_CATEGORIES:
            await self.conn.execute(
                """
                INSERT OR IGNORE INTO ticket_categories (guild_id, name, emoji, description)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, name, emoji, desc),
            )
        await self.conn.execute(
            """
            UPDATE ticket_config
            SET name_template = '・{step}・{category}-{number}'
            WHERE guild_id = ? AND name_template IN ('ticket-{number}', '{category}-{number}')
            """,
            (guild_id,),
        )
        await self.conn.commit()

    async def get_ticket_config(self, guild_id: int) -> aiosqlite.Row:
        await self.ensure_ticket_config(guild_id)
        cursor = await self.conn.execute(
            "SELECT * FROM ticket_config WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        return row

    async def update_ticket_config(self, guild_id: int, **fields: object) -> None:
        await self.ensure_ticket_config(guild_id)
        allowed = {
            "discord_category_id",
            "log_channel_id",
            "panel_channel_id",
            "panel_message_id",
            "name_template",
            "max_open_per_user",
            "counter",
            "opener_can_close",
            "idle_close_hours",
            "remind_unclaimed_hours",
        }
        parts: list[str] = []
        values: list[object] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return
        values.append(guild_id)
        await self.conn.execute(
            f"UPDATE ticket_config SET {', '.join(parts)} WHERE guild_id = ?",
            values,
        )
        await self.conn.commit()

    async def next_ticket_number(self, guild_id: int) -> int:
        await self.ensure_ticket_config(guild_id)
        await self.conn.execute(
            "UPDATE ticket_config SET counter = counter + 1 WHERE guild_id = ?",
            (guild_id,),
        )
        cursor = await self.conn.execute(
            "SELECT counter FROM ticket_config WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        await self.conn.commit()
        return int(row[0]) if row else 1

    async def add_ticket_staff_role(self, guild_id: int, role_id: int) -> None:
        await self.ensure_ticket_config(guild_id)
        await self.conn.execute(
            "INSERT OR IGNORE INTO ticket_staff_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        await self.conn.commit()

    async def remove_ticket_staff_role(self, guild_id: int, role_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM ticket_staff_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def list_ticket_staff_roles(self, guild_id: int) -> list[int]:
        cursor = await self.conn.execute(
            "SELECT role_id FROM ticket_staff_roles WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        return [int(r[0]) for r in rows]

    async def list_ticket_categories(
        self, guild_id: int, *, enabled_only: bool = True
    ) -> list[aiosqlite.Row]:
        await self.ensure_ticket_config(guild_id)
        clause = "AND enabled = 1" if enabled_only else ""
        cursor = await self.conn.execute(
            f"""
            SELECT * FROM ticket_categories
            WHERE guild_id = ? {clause}
            ORDER BY id
            """,
            (guild_id,),
        )
        return await cursor.fetchall()

    async def add_ticket_category(
        self,
        guild_id: int,
        name: str,
        *,
        emoji: str = "📩",
        description: str = "",
    ) -> int | None:
        await self.ensure_ticket_config(guild_id)
        try:
            cursor = await self.conn.execute(
                """
                INSERT INTO ticket_categories (guild_id, name, emoji, description)
                VALUES (?, ?, ?, ?)
                """,
                (guild_id, name.strip(), emoji.strip() or "📩", description.strip()),
            )
            await self.conn.commit()
            return int(cursor.lastrowid)
        except aiosqlite.IntegrityError:
            return None

    async def remove_ticket_category(self, guild_id: int, category_id: int) -> bool:
        open_count = await self.count_open_tickets_for_category(guild_id, category_id)
        if open_count > 0:
            return False
        cursor = await self.conn.execute(
            "DELETE FROM ticket_categories WHERE guild_id = ? AND id = ?",
            (guild_id, category_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def set_ticket_category_enabled(
        self, guild_id: int, category_id: int, *, enabled: bool
    ) -> bool:
        cursor = await self.conn.execute(
            """
            UPDATE ticket_categories SET enabled = ?
            WHERE guild_id = ? AND id = ?
            """,
            (int(enabled), guild_id, category_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def count_open_tickets_for_category(self, guild_id: int, category_id: int) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) FROM tickets
            WHERE guild_id = ? AND category_id = ? AND status = 'open'
            """,
            (guild_id, category_id),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def get_ticket_category(self, category_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM ticket_categories WHERE id = ?",
            (category_id,),
        )
        return await cursor.fetchone()

    async def count_open_tickets(self, guild_id: int, opener_id: int) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) FROM tickets
            WHERE guild_id = ? AND opener_id = ? AND status = 'open'
            """,
            (guild_id, opener_id),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def create_ticket(
        self,
        *,
        guild_id: int,
        category_id: int | None,
        channel_id: int,
        opener_id: int,
        opener_name: str,
        subject: str | None = None,
        ticket_number: int | None = None,
        control_message_id: int | None = None,
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO tickets (
                guild_id, category_id, channel_id, opener_id, opener_name,
                subject, ticket_number, control_message_id, last_activity_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                guild_id,
                category_id,
                channel_id,
                opener_id,
                opener_name,
                subject,
                ticket_number,
                control_message_id,
            ),
        )
        await self.conn.commit()
        return int(cursor.lastrowid)

    async def get_ticket_by_channel(self, channel_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM tickets WHERE channel_id = ?",
            (channel_id,),
        )
        return await cursor.fetchone()

    async def get_ticket(self, ticket_id: int) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            "SELECT * FROM tickets WHERE id = ?",
            (ticket_id,),
        )
        return await cursor.fetchone()

    async def claim_ticket(self, ticket_id: int, staff_id: int) -> bool:
        cursor = await self.conn.execute(
            """
            UPDATE tickets SET claimed_by_id = ?
            WHERE id = ? AND status = 'open' AND claimed_by_id IS NULL
            """,
            (staff_id, ticket_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def unclaim_ticket(self, ticket_id: int) -> bool:
        cursor = await self.conn.execute(
            """
            UPDATE tickets SET claimed_by_id = NULL
            WHERE id = ? AND status = 'open' AND claimed_by_id IS NOT NULL
            """,
            (ticket_id,),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def set_control_message_id(self, ticket_id: int, message_id: int) -> None:
        await self.conn.execute(
            "UPDATE tickets SET control_message_id = ? WHERE id = ?",
            (message_id, ticket_id),
        )
        await self.conn.commit()

    async def touch_ticket_activity(self, channel_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE tickets SET last_activity_at = datetime('now')
            WHERE channel_id = ? AND status = 'open'
            """,
            (channel_id,),
        )
        await self.conn.commit()

    async def mark_staff_ping(self, ticket_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE tickets SET last_staff_ping_at = datetime('now')
            WHERE id = ?
            """,
            (ticket_id,),
        )
        await self.conn.commit()

    async def guilds_with_open_tickets(self) -> list[int]:
        cursor = await self.conn.execute(
            "SELECT DISTINCT guild_id FROM tickets WHERE status = 'open'"
        )
        rows = await cursor.fetchall()
        return [int(r[0]) for r in rows]

    async def close_ticket(
        self,
        ticket_id: int,
        *,
        closed_by_id: int,
        reason: str,
        transcript: str | None = None,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE tickets
            SET status = 'closed',
                closed_at = datetime('now'),
                closed_by_id = ?,
                close_reason = ?,
                transcript = ?
            WHERE id = ?
            """,
            (closed_by_id, reason, transcript, ticket_id),
        )
        await self.conn.commit()

    async def close_ticket_orphan(self, ticket_id: int, *, reason: str) -> bool:
        cursor = await self.conn.execute(
            """
            UPDATE tickets
            SET status = 'closed',
                closed_at = datetime('now'),
                close_reason = ?,
                transcript = NULL
            WHERE id = ? AND status = 'open'
            """,
            (reason, ticket_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def list_open_tickets(self, guild_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM tickets
            WHERE guild_id = ? AND status = 'open'
            ORDER BY datetime(created_at) DESC
            """,
            (guild_id,),
        )
        return await cursor.fetchall()

    async def list_tickets(
        self,
        guild_id: int,
        *,
        status: str | None = None,
        limit: int = 15,
        offset: int = 0,
    ) -> list[aiosqlite.Row]:
        if status:
            cursor = await self.conn.execute(
                """
                SELECT * FROM tickets
                WHERE guild_id = ? AND status = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ? OFFSET ?
                """,
                (guild_id, status, limit, offset),
            )
        else:
            cursor = await self.conn.execute(
                """
                SELECT * FROM tickets
                WHERE guild_id = ?
                ORDER BY datetime(created_at) DESC
                LIMIT ? OFFSET ?
                """,
                (guild_id, limit, offset),
            )
        return await cursor.fetchall()

    async def get_ticket_by_number(
        self, guild_id: int, ticket_number: int
    ) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(
            """
            SELECT * FROM tickets
            WHERE guild_id = ? AND ticket_number = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (guild_id, ticket_number),
        )
        return await cursor.fetchone()

    async def reopen_ticket(self, ticket_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE tickets
            SET status = 'open',
                closed_at = NULL,
                closed_by_id = NULL,
                close_reason = NULL,
                claimed_by_id = NULL
            WHERE id = ?
            """,
            (ticket_id,),
        )
        await self.conn.commit()

    async def ticket_statistics(self, guild_id: int) -> dict[str, int]:
        cursor = await self.conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count,
                SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed_count,
                SUM(CASE WHEN status = 'open' AND claimed_by_id IS NOT NULL THEN 1 ELSE 0 END)
                    AS claimed_open,
                COUNT(*) AS total
            FROM tickets WHERE guild_id = ?
            """,
            (guild_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else {
            "open_count": 0,
            "closed_count": 0,
            "claimed_open": 0,
            "total": 0,
        }

    async def guilds_with_ticket_panels(self) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM ticket_config
            WHERE panel_message_id IS NOT NULL AND panel_channel_id IS NOT NULL
            """
        )
        return await cursor.fetchall()

    # --- Mod calls ---

    async def ensure_mod_call_config(self, guild_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO mod_call_config (guild_id) VALUES (?)",
            (guild_id,),
        )
        await self.conn.commit()

    async def get_mod_call_config(self, guild_id: int) -> aiosqlite.Row:
        await self.ensure_mod_call_config(guild_id)
        cursor = await self.conn.execute(
            "SELECT * FROM mod_call_config WHERE guild_id = ?",
            (guild_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        return row

    async def update_mod_call_config(self, guild_id: int, **fields: object) -> None:
        await self.ensure_mod_call_config(guild_id)
        allowed = {"channel_id", "cooldown_seconds", "enabled"}
        parts: list[str] = []
        values: list[object] = []
        for key, value in fields.items():
            if key not in allowed:
                continue
            parts.append(f"{key} = ?")
            values.append(value)
        if not parts:
            return
        values.append(guild_id)
        await self.conn.execute(
            f"UPDATE mod_call_config SET {', '.join(parts)} WHERE guild_id = ?",
            values,
        )
        await self.conn.commit()

    async def add_mod_call_role(self, guild_id: int, role_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO mod_call_roles (guild_id, role_id) VALUES (?, ?)",
            (guild_id, role_id),
        )
        await self.conn.commit()

    async def remove_mod_call_role(self, guild_id: int, role_id: int) -> bool:
        cursor = await self.conn.execute(
            "DELETE FROM mod_call_roles WHERE guild_id = ? AND role_id = ?",
            (guild_id, role_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def list_mod_call_roles(self, guild_id: int) -> list[int]:
        cursor = await self.conn.execute(
            "SELECT role_id FROM mod_call_roles WHERE guild_id = ?",
            (guild_id,),
        )
        rows = await cursor.fetchall()
        return [int(r[0]) for r in rows]

    async def mod_call_cooldown_remaining(self, guild_id: int, user_id: int) -> int:
        config = await self.get_mod_call_config(guild_id)
        cooldown = int(config["cooldown_seconds"] or 0)
        if cooldown <= 0:
            return 0
        cursor = await self.conn.execute(
            """
            SELECT CAST(
                (julianday(datetime('now')) - julianday(last_called_at)) * 86400 AS INTEGER
            )
            FROM mod_call_cooldowns
            WHERE guild_id = ? AND user_id = ?
            """,
            (guild_id, user_id),
        )
        row = await cursor.fetchone()
        if not row or row[0] is None:
            return 0
        elapsed = int(row[0])
        return max(0, cooldown - elapsed)

    async def touch_mod_call_cooldown(self, guild_id: int, user_id: int) -> None:
        await self.conn.execute(
            """
            INSERT INTO mod_call_cooldowns (guild_id, user_id, last_called_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(guild_id, user_id) DO UPDATE SET last_called_at = datetime('now')
            """,
            (guild_id, user_id),
        )
        await self.conn.commit()
