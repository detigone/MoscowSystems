from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from bot.db.schema import DEFAULT_POINT_RULES, SCHEMA

logger = logging.getLogger(__name__)

_LIKE_ESCAPE = re.compile(r"([%_\\])")


def escape_like(value: str) -> str:
    return _LIKE_ESCAPE.sub(r"\\\1", value)


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.executescript(SCHEMA)
        await self.conn.execute("DROP TABLE IF EXISTS punishments_new")
        await self._migrate_punishment_columns()
        await self._migrate_punishments_unique()
        await self.conn.commit()

    async def _migrate_punishment_columns(self) -> None:
        assert self.conn is not None
        cursor = await self.conn.execute("PRAGMA table_info(punishments)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "description" not in columns:
            await self.conn.execute("ALTER TABLE punishments ADD COLUMN description TEXT")
        if "expires_at" not in columns:
            await self.conn.execute("ALTER TABLE punishments ADD COLUMN expires_at TEXT")

    async def _migrate_punishments_unique(self) -> None:
        assert self.conn is not None
        cursor = await self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='punishments'"
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            return
        ddl = row[0]
        if "UNIQUE (guild_id, cycle_case_id)" in ddl:
            return
        if "cycle_case_id TEXT NOT NULL UNIQUE" not in ddl and "cycle_case_id TEXT UNIQUE" not in ddl:
            return

        logger.info("Migrating punishments table: per-guild cycle_case_id uniqueness")
        cursor = await self.conn.execute("PRAGMA table_info(punishments)")
        src_cols = {row[1] for row in await cursor.fetchall()}

        dest_cols = (
            "id",
            "guild_id",
            "cycle_case_id",
            "cycle_snowflake",
            "roblox_id",
            "roblox_name",
            "type_key",
            "reason",
            "description",
            "points",
            "staff_discord_id",
            "staff_name",
            "created_at",
            "expires_at",
            "revoked_at",
            "revoked_by_discord_id",
            "revoked_by_name",
        )
        select_exprs = []
        for col in dest_cols:
            if col in src_cols:
                select_exprs.append(col)
            else:
                select_exprs.append("NULL")

        col_list = ", ".join(dest_cols)
        select_list = ", ".join(select_exprs)
        await self.conn.executescript(
            f"""
            CREATE TABLE punishments_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                cycle_case_id TEXT NOT NULL,
                cycle_snowflake TEXT,
                roblox_id INTEGER NOT NULL,
                roblox_name TEXT NOT NULL,
                type_key TEXT NOT NULL,
                reason TEXT,
                description TEXT,
                points INTEGER NOT NULL,
                staff_discord_id INTEGER,
                staff_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT,
                revoked_at TEXT,
                revoked_by_discord_id INTEGER,
                revoked_by_name TEXT,
                UNIQUE (guild_id, cycle_case_id)
            );
            INSERT OR IGNORE INTO punishments_new ({col_list})
                SELECT {select_list} FROM punishments;
            DROP TABLE punishments;
            ALTER TABLE punishments_new RENAME TO punishments;
            CREATE INDEX IF NOT EXISTS idx_punishments_guild_roblox
                ON punishments (guild_id, roblox_id);
            CREATE INDEX IF NOT EXISTS idx_punishments_guild_roblox_active
                ON punishments (guild_id, roblox_id, revoked_at);
            CREATE INDEX IF NOT EXISTS idx_punishments_guild_name
                ON punishments (guild_id, roblox_name COLLATE NOCASE);
            """
        )

    async def close(self) -> None:
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def ensure_guild(self, guild_id: int) -> None:
        assert self.conn is not None
        for type_key, points in DEFAULT_POINT_RULES:
            await self.conn.execute(
                """
                INSERT OR IGNORE INTO point_rules (guild_id, type_key, points)
                VALUES (?, ?, ?)
                """,
                (guild_id, type_key, points),
            )
        await self.conn.commit()

    async def points_for_type(self, guild_id: int, type_name: str) -> int:
        await self.ensure_guild(guild_id)
        assert self.conn is not None
        key = type_name.strip().lower()
        cursor = await self.conn.execute(
            "SELECT points FROM point_rules WHERE guild_id = ? AND type_key = ?",
            (guild_id, key),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def create_punishment(
        self,
        *,
        guild_id: int,
        cycle_case_id: str,
        cycle_snowflake: str | None,
        roblox_id: int,
        roblox_name: str,
        type_name: str,
        reason: str,
        description: str | None = None,
        staff_discord_id: int | None,
        staff_name: str | None,
        created_at_epoch: int | None = None,
        expires_at: str | None = None,
    ) -> int | None:
        await self.ensure_guild(guild_id)
        assert self.conn is not None
        type_key = type_name.strip().lower()
        points = await self.points_for_type(guild_id, type_key)

        if created_at_epoch:
            created_at = datetime.fromtimestamp(created_at_epoch, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            created_at = None

        await self.conn.execute("BEGIN IMMEDIATE")
        try:
            if created_at:
                cursor = await self.conn.execute(
                    """
                    INSERT INTO punishments (
                        guild_id, cycle_case_id, cycle_snowflake, roblox_id, roblox_name,
                        type_key, reason, description, points, staff_discord_id, staff_name,
                        created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        cycle_case_id,
                        cycle_snowflake,
                        roblox_id,
                        roblox_name,
                        type_key,
                        reason,
                        description,
                        points,
                        staff_discord_id,
                        staff_name,
                        created_at,
                        expires_at,
                    ),
                )
            else:
                cursor = await self.conn.execute(
                    """
                    INSERT INTO punishments (
                        guild_id, cycle_case_id, cycle_snowflake, roblox_id, roblox_name,
                        type_key, reason, description, points, staff_discord_id, staff_name,
                        expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        cycle_case_id,
                        cycle_snowflake,
                        roblox_id,
                        roblox_name,
                        type_key,
                        reason,
                        description,
                        points,
                        staff_discord_id,
                        staff_name,
                        expires_at,
                    ),
                )
            await self.conn.commit()
            return int(cursor.lastrowid)
        except aiosqlite.IntegrityError:
            await self.conn.rollback()
            return None
        except Exception:
            await self.conn.rollback()
            raise

    async def revoke_punishment(
        self,
        *,
        guild_id: int,
        cycle_case_id: str,
        revoked_by_discord_id: int | None,
        revoked_by_name: str | None,
    ) -> bool:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            UPDATE punishments
            SET revoked_at = datetime('now'),
                revoked_by_discord_id = ?,
                revoked_by_name = ?
            WHERE guild_id = ? AND cycle_case_id = ? AND revoked_at IS NULL
            """,
            (revoked_by_discord_id, revoked_by_name, guild_id, cycle_case_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def sum_points(self, guild_id: int, roblox_id: int) -> int:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT COALESCE(SUM(points), 0) FROM punishments
            WHERE guild_id = ? AND roblox_id = ? AND revoked_at IS NULL
            """,
            (guild_id, roblox_id),
        )
        row = await cursor.fetchone()
        return int(row[0]) if row else 0

    async def punishment_breakdown(self, guild_id: int, roblox_id: int) -> list[dict[str, Any]]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT type_key, COUNT(*) AS qty, COALESCE(SUM(points), 0) AS points
            FROM punishments
            WHERE guild_id = ? AND roblox_id = ? AND revoked_at IS NULL
            GROUP BY type_key
            ORDER BY points DESC
            """,
            (guild_id, roblox_id),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def list_punishments(
        self,
        guild_id: int,
        roblox_id: int,
        *,
        include_revoked: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        assert self.conn is not None
        revoked_clause = "" if include_revoked else "AND revoked_at IS NULL"
        cursor = await self.conn.execute(
            f"""
            SELECT *
            FROM punishments
            WHERE guild_id = ? AND roblox_id = ? {revoked_clause}
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (guild_id, roblox_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def search_names(self, guild_id: int, query: str, limit: int = 15) -> list[str]:
        assert self.conn is not None
        pattern = f"%{escape_like(query.strip())}%"
        cursor = await self.conn.execute(
            """
            SELECT DISTINCT roblox_name FROM punishments
            WHERE guild_id = ? AND roblox_name LIKE ? ESCAPE '\\'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (guild_id, pattern, limit),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def recent_moderated_names(self, guild_id: int, limit: int = 15) -> list[str]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT roblox_name FROM punishments
            WHERE guild_id = ?
            GROUP BY roblox_name
            ORDER BY MAX(created_at) DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def get_point_rules(self, guild_id: int) -> list[dict[str, Any]]:
        await self.ensure_guild(guild_id)
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT type_key, points FROM point_rules
            WHERE guild_id = ?
            ORDER BY points DESC, type_key
            """,
            (guild_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def set_point_rule(self, guild_id: int, type_key: str, points: int) -> None:
        await self.ensure_guild(guild_id)
        assert self.conn is not None
        await self.conn.execute(
            """
            INSERT INTO point_rules (guild_id, type_key, points)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, type_key) DO UPDATE SET points = excluded.points
            """,
            (guild_id, type_key.strip().lower(), max(0, points)),
        )
        await self.conn.commit()

    async def leaderboard(
        self, guild_id: int, *, limit: int = 10, min_points: int = 1
    ) -> list[dict[str, Any]]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT roblox_id, roblox_name,
                   COALESCE(SUM(points), 0) AS total_points,
                   COUNT(*) AS active_count
            FROM punishments
            WHERE guild_id = ? AND revoked_at IS NULL
            GROUP BY roblox_id
            HAVING total_points >= ?
            ORDER BY total_points DESC, active_count DESC
            LIMIT ?
            """,
            (guild_id, min_points, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def radar_players(
        self, guild_id: int, *, min_points: int = 5, limit: int = 15
    ) -> list[dict[str, Any]]:
        return await self.leaderboard(guild_id, limit=limit, min_points=min_points)

    async def recent_punishments(
        self, guild_id: int, *, limit: int = 12, include_revoked: bool = False
    ) -> list[dict[str, Any]]:
        assert self.conn is not None
        revoked_clause = "" if include_revoked else "AND revoked_at IS NULL"
        cursor = await self.conn.execute(
            f"""
            SELECT * FROM punishments
            WHERE guild_id = ? {revoked_clause}
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def guild_statistics(self, guild_id: int) -> dict[str, Any]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT
                COUNT(*) AS total_records,
                SUM(CASE WHEN revoked_at IS NULL THEN 1 ELSE 0 END) AS active_count,
                SUM(CASE WHEN revoked_at IS NOT NULL THEN 1 ELSE 0 END) AS revoked_count,
                COALESCE(SUM(CASE WHEN revoked_at IS NULL THEN points ELSE 0 END), 0) AS active_points,
                COUNT(DISTINCT roblox_id) AS unique_players,
                COUNT(DISTINCT staff_discord_id) AS unique_staff
            FROM punishments WHERE guild_id = ?
            """,
            (guild_id,),
        )
        row = await cursor.fetchone()
        stats = dict(row) if row else {}

        cursor = await self.conn.execute(
            """
            SELECT type_key, COUNT(*) AS qty
            FROM punishments
            WHERE guild_id = ? AND revoked_at IS NULL
            GROUP BY type_key
            ORDER BY qty DESC
            LIMIT 5
            """,
            (guild_id,),
        )
        stats["top_types"] = [dict(r) for r in await cursor.fetchall()]

        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT roblox_id FROM punishments
                WHERE guild_id = ? AND revoked_at IS NULL
                GROUP BY roblox_id
                HAVING SUM(points) >= 10
            )
            """,
            (guild_id,),
        )
        high_risk_row = await cursor.fetchone()
        stats["high_risk_players"] = int(high_risk_row[0]) if high_risk_row else 0
        return stats

    async def moderator_leaderboard(self, guild_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT staff_discord_id, staff_name,
                   COUNT(*) AS cases,
                   COALESCE(SUM(points), 0) AS points_given
            FROM punishments
            WHERE guild_id = ? AND staff_discord_id IS NOT NULL
            GROUP BY staff_discord_id
            ORDER BY cases DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def moderator_stats(self, guild_id: int, staff_discord_id: int) -> dict[str, Any]:
        assert self.conn is not None
        cursor = await self.conn.execute(
            """
            SELECT staff_name,
                   COUNT(*) AS total_cases,
                   SUM(CASE WHEN revoked_at IS NULL THEN 1 ELSE 0 END) AS active_cases,
                   COALESCE(SUM(points), 0) AS points_given
            FROM punishments
            WHERE guild_id = ? AND staff_discord_id = ?
            """,
            (guild_id, staff_discord_id),
        )
        row = await cursor.fetchone()
        if not row or not row["total_cases"]:
            return {}
        result = dict(row)

        cursor = await self.conn.execute(
            """
            SELECT type_key, COUNT(*) AS qty
            FROM punishments
            WHERE guild_id = ? AND staff_discord_id = ?
            GROUP BY type_key
            ORDER BY qty DESC
            LIMIT 5
            """,
            (guild_id, staff_discord_id),
        )
        result["by_type"] = [dict(r) for r in await cursor.fetchall()]
        return result
