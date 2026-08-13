from __future__ import annotations

import aiosqlite

from bot.db.schema import PUNISHMENT_TYPE_POINTS, SCHEMA


def normalize_type(type_name: str) -> str:
    key = type_name.strip().lower()
    aliases = {
        "warn": "warning",
        "warning": "warning",
        "kick": "kick",
        "ban": "ban",
        "bolo": "bolo",
    }
    return aliases.get(key, key)


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

    async def get_type_points(self, guild_id: int, type_name: str) -> int:
        key = normalize_type(type_name)
        cursor = await self.conn.execute(
            """
            SELECT points FROM punishment_type_points
            WHERE guild_id = ? AND type_key = ?
            """,
            (guild_id, key),
        )
        row = await cursor.fetchone()
        if row:
            return int(row["points"])
        return PUNISHMENT_TYPE_POINTS.get(key, 0)

    async def create_punishment(
        self,
        *,
        guild_id: int,
        cycle_case_id: str,
        cycle_snowflake: int | None,
        roblox_id: int,
        roblox_name: str,
        type_name: str,
        reason: str,
        staff_discord_id: int | None,
        staff_name: str | None,
    ) -> int | None:
        points = await self.get_type_points(guild_id, type_name)
        type_key = normalize_type(type_name)
        try:
            cursor = await self.conn.execute(
                """
                INSERT INTO punishments
                (guild_id, cycle_case_id, cycle_snowflake, roblox_id, roblox_name,
                 type_key, reason, points, staff_discord_id, staff_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    cycle_case_id,
                    cycle_snowflake,
                    roblox_id,
                    roblox_name,
                    type_key,
                    reason,
                    points,
                    staff_discord_id,
                    staff_name,
                ),
            )
        except aiosqlite.IntegrityError:
            return None

        punishment_id = cursor.lastrowid
        if points:
            await self.conn.execute(
                """
                INSERT INTO points_ledger
                (guild_id, roblox_id, delta, reason, source_type, source_id, staff_discord_id)
                VALUES (?, ?, ?, ?, 'punish', ?, ?)
                """,
                (guild_id, roblox_id, points, reason, punishment_id, staff_discord_id),
            )

        await self.conn.execute(
            """
            INSERT INTO recent_moderated (guild_id, roblox_name, roblox_id, moderated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(guild_id, roblox_name) DO UPDATE SET
                roblox_id = excluded.roblox_id,
                moderated_at = datetime('now')
            """,
            (guild_id, roblox_name, roblox_id),
        )
        await self.conn.commit()
        return punishment_id

    async def revoke_punishment(
        self,
        *,
        guild_id: int,
        cycle_case_id: str,
        revoked_by_discord_id: int | None,
        revoked_by_name: str | None,
    ) -> bool:
        cursor = await self.conn.execute(
            """
            SELECT id, roblox_id, points, revoked FROM punishments
            WHERE guild_id = ? AND cycle_case_id = ?
            """,
            (guild_id, cycle_case_id),
        )
        row = await cursor.fetchone()
        if not row or row["revoked"]:
            return False

        await self.conn.execute(
            """
            UPDATE punishments SET
                revoked = 1,
                revoked_at = datetime('now'),
                revoked_by_discord_id = ?,
                revoked_by_name = ?
            WHERE id = ?
            """,
            (revoked_by_discord_id, revoked_by_name, row["id"]),
        )
        if row["points"]:
            await self.conn.execute(
                """
                INSERT INTO points_ledger
                (guild_id, roblox_id, delta, reason, source_type, source_id, staff_discord_id)
                VALUES (?, ?, ?, ?, 'revoke', ?, ?)
                """,
                (
                    guild_id,
                    row["roblox_id"],
                    -int(row["points"]),
                    "Revoked punishment",
                    row["id"],
                    revoked_by_discord_id,
                ),
            )
        await self.conn.commit()
        return True

    async def sum_points(self, guild_id: int, roblox_id: int) -> int:
        cursor = await self.conn.execute(
            """
            SELECT COALESCE(SUM(delta), 0) AS total
            FROM points_ledger WHERE guild_id = ? AND roblox_id = ?
            """,
            (guild_id, roblox_id),
        )
        row = await cursor.fetchone()
        return int(row["total"]) if row else 0

    async def punishment_breakdown(self, guild_id: int, roblox_id: int) -> list[aiosqlite.Row]:
        cursor = await self.conn.execute(
            """
            SELECT type_key, COUNT(*) AS qty, COALESCE(SUM(points), 0) AS points
            FROM punishments
            WHERE guild_id = ? AND roblox_id = ? AND revoked = 0
            GROUP BY type_key
            """,
            (guild_id, roblox_id),
        )
        return await cursor.fetchall()

    async def recent_moderated_names(self, guild_id: int, limit: int = 20) -> list[str]:
        cursor = await self.conn.execute(
            """
            SELECT roblox_name FROM recent_moderated
            WHERE guild_id = ?
            ORDER BY moderated_at DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        rows = await cursor.fetchall()
        return [row["roblox_name"] for row in rows]

    async def search_names(self, guild_id: int, query: str, limit: int = 15) -> list[str]:
        cursor = await self.conn.execute(
            """
            SELECT DISTINCT roblox_name FROM punishments
            WHERE guild_id = ? AND roblox_name LIKE ?
            ORDER BY roblox_name
            LIMIT ?
            """,
            (guild_id, f"%{query}%", limit),
        )
        rows = await cursor.fetchall()
        return [row["roblox_name"] for row in rows]
